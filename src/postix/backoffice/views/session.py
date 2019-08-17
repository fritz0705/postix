from contextlib import suppress
from typing import Union

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import QuerySet, Sum
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from django.views.generic import DetailView, TemplateView
from django.views.generic.list import ListView

from postix.core.utils.flow import FlowError, reverse_session

from ...core.models import (
    Cashdesk, CashdeskSession, CashMovement, ItemMovement, Record, User,
)
from .. import checks
from ..forms import (
    ItemMovementFormSetHelper, SessionBaseForm, get_form_and_formset,
)
from ..report import generate_record
from .utils import BackofficeUserRequiredMixin, backoffice_user_required


class NewSessionView(LoginRequiredMixin, BackofficeUserRequiredMixin, TemplateView):
    template_name = 'backoffice/new_session.html'

    def get_form_and_formset(self):
        if self.request.method == 'POST':
            form, formset = get_form_and_formset(
                request=self.request, must_be_positive=True
            )
            with suppress(Exception):
                if not Cashdesk.objects.get(
                    pk=form.data.get('session-cashdesk')
                ).handles_items:
                    formset = None
            return form, formset
        form, formset = get_form_and_formset(
            initial_form={'backoffice_user': self.request.user}, must_be_positive=True
        )
        param = self.request.GET.get('desk')
        if param:
            with suppress(Exception):
                initial_form = {
                    'cashdesk': Cashdesk.objects.get(pk=int(param)),
                    'backoffice_user': self.request.user,
                }
                form, _ignored = get_form_and_formset(
                    initial_form=initial_form, must_be_positive=True
                )
                if not initial_form['cashdesk'].handles_items:
                    formset = None
        return form, formset

    @transaction.atomic
    def post(self, request: HttpRequest, *args, **kwargs):
        form, formset = self.get_form_and_formset()
        if not form.is_valid() or (formset and not formset.is_valid()):
            messages.error(
                request, _('Session could not be created. Please review the data.')
            )
            return self.render_to_response(self.get_context_data())
        session = CashdeskSession.objects.create(
            cashdesk=form.cleaned_data['cashdesk'],
            user=form.cleaned_data['user']
            if form.cleaned_data['cashdesk'].ip_address
            else None,
            start=now(),
            backoffice_user_before=form.cleaned_data['backoffice_user'],
        )
        record = None
        if form.cleaned_data['cash_before']:
            movement = CashMovement.objects.create(
                session=session,
                cash=form.cleaned_data['cash_before'],
                backoffice_user=form.cleaned_data['backoffice_user'],
            )
            record = movement.create_record(
                carrier=form.cleaned_data['user']
                if not form.cleaned_data['cashdesk'].ip_address
                else None
            )
        if formset:
            for f in formset:
                item = f.cleaned_data.get('item')
                amount = f.cleaned_data.get('amount')
                if item and amount and amount > 0:
                    if not form.cleaned_data['cashdesk'].handles_items:
                        messages.error(request, _('You cannot add items to this cashdesk!'))
                        return self.render_to_response(self.get_context_data())
                    ItemMovement.objects.create(
                        item=item,
                        session=session,
                        amount=amount,
                        backoffice_user=form.cleaned_data['backoffice_user'],
                    )
        if record:
            return redirect('backoffice:record-print', pk=record.pk)
        return redirect('backoffice:session-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form, formset = self.get_form_and_formset()
        context['form'] = form
        context['formset'] = formset
        context['helper'] = ItemMovementFormSetHelper()
        context['users'] = User.objects.values_list('username', flat=True)
        context['backoffice_users'] = User.objects.filter(
            is_backoffice_user=True
        ).values_list('username', flat=True)
        return context


class SessionListView(LoginRequiredMixin, BackofficeUserRequiredMixin, ListView):
    """ Implements only a list of active sessions for now. Ended sessions will
    be visible in the reports view """

    model = CashdeskSession
    template_name = 'backoffice/session_list.html'
    context_object_name = 'cashdesks'

    def get_queryset(self) -> QuerySet:
        return Cashdesk.objects.filter(is_active=True).order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['check_errors'] = checks.all_errors()
        return ctx


class ReportListView(LoginRequiredMixin, BackofficeUserRequiredMixin, ListView):
    """ List of old sessions """

    model = CashdeskSession
    template_name = 'backoffice/report_list.html'
    context_object_name = 'sessions'
    paginate_by = 25

    def get_queryset(self) -> QuerySet:
        return CashdeskSession.objects.filter(end__isnull=False).order_by('-end')


class SessionDetailView(BackofficeUserRequiredMixin, DetailView):
    queryset = CashdeskSession.objects.all()
    template_name = 'backoffice/session_detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = self.get_object()
        ctx['url'] = self.request.build_absolute_uri('/')
        ctx['total'] = (session.cash_after or 0) - (session.cash_before or 0)
        return ctx


@backoffice_user_required
@transaction.atomic
def resupply_session(
    request: HttpRequest, pk: int
) -> Union[HttpResponse, HttpResponseRedirect]:
    """ TODO: show approximate current amounts of items? """
    session = get_object_or_404(CashdeskSession, pk=pk)
    initial_form = {
        'cashdesk': session.cashdesk,
        'user': session.user if session.cashdesk.ip_address else '',
        'backoffice_user': request.user,
        'cash_before': 0,
    }
    form, formset = get_form_and_formset(initial_form=initial_form)
    if not session.cashdesk.handles_items:
        formset = None

    if request.method == 'POST':
        form, formset = get_form_and_formset(request=request)
        if not session.cashdesk.handles_items:
            formset = None

        if (not formset or formset.is_valid()) and form.is_valid():
            record = None
            if form.cleaned_data.get('cash_before'):
                movement = CashMovement.objects.create(
                    cash=form.cleaned_data.get('cash_before'),
                    session=session,
                    backoffice_user=form.cleaned_data['backoffice_user'],
                )
                record = movement.create_record(
                    carrier=form.cleaned_data['user']
                    if not form.cleaned_data['cashdesk'].ip_address
                    else None
                )
            if formset:
                for f in formset:
                    item = f.cleaned_data.get('item')
                    amount = f.cleaned_data.get('amount')
                    if item and amount:
                        ItemMovement.objects.create(
                            item=item,
                            session=session,
                            amount=amount,
                            backoffice_user=form.cleaned_data['backoffice_user'],
                        )
            messages.success(request, _('Products have been added to the cashdesk.'))
            if record:
                return redirect('backoffice:record-print', pk=record.pk)
            return redirect('backoffice:session-detail', pk=pk)

        else:
            messages.error(request, _('Error: Please review the data.'))

    form.fields['user'].widget.attrs['readonly'] = bool(session.cashdesk.ip_address)
    form.fields['cashdesk'].widget.attrs['readonly'] = True
    # form.fields['cash_before'].widget = forms.HiddenInput()

    return render(
        request,
        'backoffice/resupply_session.html',
        {
            'formset': formset,
            'helper': ItemMovementFormSetHelper(),
            'form': form,
            'backoffice_users': User.objects.filter(
                is_backoffice_user=True
            ).values_list('username', flat=True),
        },
    )


@backoffice_user_required
def reverse_session_view(
    request: HttpRequest, pk: int
) -> Union[HttpRequest, HttpResponseRedirect]:
    session = get_object_or_404(CashdeskSession, pk=pk)

    if request.method == 'POST':
        try:
            reverse_session(session)
        except FlowError as e:
            messages.error(request, str(e))
        else:
            messages.success(
                request, _('All transactions in the session have been cancelled.')
            )
        return redirect('backoffice:session-detail', pk=pk)

    elif request.method == 'GET':
        return render(request, 'backoffice/reverse_session.html', {'session': session})


class EndSessionView(LoginRequiredMixin, BackofficeUserRequiredMixin, TemplateView):
    template_name = 'backoffice/end_session.html'

    def get_object(self):
        return get_object_or_404(CashdeskSession, pk=self.kwargs.get('pk'))

    def get_form_and_formset(self):
        session = self.get_object()
        item_data = session.get_current_items()
        if self.request.method == 'POST':
            form, formset = get_form_and_formset(request=self.request, extra=0)
        else:
            form, formset = get_form_and_formset(
                extra=0,
                initial_form={
                    'cashdesk': session.cashdesk,
                    'user': session.user,
                    'backoffice_user': self.request.user,
                    'cash_before': session.cash_after,
                },
                initial_formset=[
                    {'item': d['item'], 'amount': d['final_movements']}
                    for d in item_data
                ],
            )
        if not session.cashdesk.handles_items:
            formset = None
        else:
            for f, item_data in zip(formset, item_data):
                f.product_label = item_data
        return form, formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.get_object()
        form, formset = self.get_form_and_formset()
        context['helper'] = ItemMovementFormSetHelper()
        context['form'] = form
        context['formset'] = formset
        context['carriers'] = set(Record.objects.all().values_list('carrier', flat=True))
        context['cash'] = {
            'initial': context['session'].cash_before,
            'transactions': context['session'].get_cash_transaction_total(),
        }
        context['backoffice_users'] = User.objects.filter(
            is_backoffice_user=True
        ).values_list('username', flat=True)
        return context

    def get(self, request, pk):
        session = self.get_object()
        if session.end:
            msg = _(
                'This session has ended already. Filling out this form will produce a corrected report. '
            )
            messages.warning(request, msg)
        form, formset = self.get_form_and_formset()
        return super().get(request, pk)

    @transaction.atomic
    def post(self, request, pk):
        session = self.get_object()
        form, formset = self.get_form_and_formset()

        if form.is_valid() and (not formset or formset.is_valid()):
            if session.end:
                # This is not optimal, but our data model does not have a way of tracking
                # cash movement over time.
                if session.cash_after != form.cleaned_data.get('cash_before'):
                    session.cash_after = form.cleaned_data.get('cash_before')
                    session.backoffice_user_after = form.cleaned_data.get(
                        'backoffice_user'
                    )
                    session.save(update_fields=['cash_after', 'backoffice_user_after'])
                    carrier = form.cleaned_data.get('user')
                    movement = session.create_final_movement(
                        carrier=carrier if isinstance(carrier, str) else None
                    )
                    record = movement.record
                else:
                    record = session.final_cash_movement.record
            else:
                session.end = now()
                session.backoffice_user_after = form.cleaned_data.get('backoffice_user')
                session.cash_after = form.cleaned_data.get('cash_before')
                session.save(
                    update_fields=['backoffice_user_after', 'cash_after', 'end']
                )
                carrier = form.cleaned_data.get('user')
                movement = session.create_final_movement(
                    carrier=carrier if isinstance(carrier, str) else None
                )
                record = movement.record
                messages.success(request, 'Session wurde beendet.')

            # It is important that we do this *after* we set session.end as the date of this movement
            # will be used in determining this as the final item takeout *after* the session.
            item_amounts = session.item_movements.values('item').annotate(
                total=Sum('amount')
            )
            item_amounts = {d['item']: d for d in session.get_current_items()}
            if formset:
                for f in formset:
                    item = f.cleaned_data.get('item')
                    amount = f.cleaned_data.get('amount')
                    previous_amount = item_amounts[item]['final_movements']
                    if item and amount and amount:
                        ItemMovement.objects.create(
                            item=item,
                            session=session,
                            amount=previous_amount - amount,
                            backoffice_user=form.cleaned_data['backoffice_user'],
                        )

            generate_record(record)
            return redirect('backoffice:record-print', pk=record.pk)
        messages.error(
            request, _('Session could not be ended: Please review the data.')
        )
        return super().post(request, pk)


@backoffice_user_required
def move_session(
    request: HttpRequest, pk: int
) -> Union[HttpRequest, HttpResponseRedirect]:
    session = get_object_or_404(CashdeskSession, pk=pk)

    if session.end:
        messages.error(request, _('Session has already ended and cannot be moved.'))

    if request.method == 'POST':
        form = SessionBaseForm(request.POST, prefix='session')

        if form.is_valid():
            session.cashdesk = form.cleaned_data.get('cashdesk')
            session.save(update_fields=['cashdesk'])
            messages.success(request, _('Session has been moved.'))
        else:
            messages.error(request, _('Session could not be moved!'))
            return redirect('backoffice:session-detail', pk=pk)

    elif request.method == 'GET':
        form = SessionBaseForm(
            prefix='session',
            initial={
                'cashdesk': session.cashdesk,
                'user': session.user,
                'backoffice_user': session.backoffice_user_before,
                'cash_before': session.cash_before,
            },
        )

    form.fields['user'].widget.attrs['readonly'] = True
    form.fields['backoffice_user'].widget = forms.HiddenInput()
    form.fields['cash_before'].widget = forms.HiddenInput()

    return render(
        request, 'backoffice/move_session.html', {'session': session, 'form': form}
    )
