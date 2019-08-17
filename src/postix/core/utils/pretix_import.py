import json
from decimal import Decimal

from django.db import transaction

from postix.core.models import Cashdesk, Preorder, PreorderPosition, Product


class FakeStyle:
    def __getattribute__(self, name):
        return lambda x: print(x)


class FakeLog:
    def write(self, string):
        if string is not None:
            print(string)


def _build_product_dict(data, log, style):
    created_items = 0
    loaded_items = 0
    product_dict = dict()
    for item in data['items']:
        if item['variations']:
            log.write(
                style.ERROR('Warning: Import script cannot deal with variations yet!')
            )

        try:
            product = Product.objects.get(import_source_id=item['id'])
            loaded_items += 1
        except Product.DoesNotExist:
            product = Product(import_source_id=item['id'])
            product.price = Decimal(item['price'])
            product.tax_rate = Decimal(item['tax_rate'])
            created_items += 1
        product.name = item['name']
        product.save()
        product_dict[item['id']] = product

    log.write(
        style.SUCCESS(
            'Found {} new and {} known products in file.'.format(
                created_items, loaded_items
            )
        )
    )
    return product_dict


@transaction.atomic
def import_pretix_data(
    data, add_cashdesks=False, log=FakeLog(), style=FakeStyle(), questions=None
):

    if isinstance(data, str):
        presale_export = json.loads(data)['event']
    elif isinstance(data, dict):
        presale_export = data['event']
    else:
        presale_export = json.load(data)['event']

    log.write(
        style.NOTICE('Importing data from event "{}".'.format(presale_export['name']))
    )

    orders = presale_export['orders']
    product_dict = _build_product_dict(presale_export, log=log, style=style)
    if isinstance(questions, str):
        questions = questions.split(',')
    questions = [int(q) for q in questions] if questions else list()
    questions = {
        element['id']: element
        for element in presale_export.get('questions', [])
        if element['id'] in questions
    }

    existing = {p.order_code: p for p in Preorder.objects.prefetch_related('positions')}

    created_orders = 0
    loaded_orders = 0
    to_insert = []
    for order in orders:
        if order['code'] in existing:
            preorder = existing[order['code']]
            created = False

            if preorder.is_paid != (order['status'] == 'p') or preorder.is_canceled != (order['status'] in ('c', 'e')):
                preorder.is_paid = order['status'] == 'p'
                preorder.is_canceled = (order['status'] in ('c', 'e'))
                preorder.save(update_fields=['is_paid', 'is_canceled'])
        else:
            preorder = Preorder.objects.create(
                order_code=order['code'],
                is_paid=(order['status'] == 'p'),
                is_canceled=(order['status'] in ('c', 'e')),
            )
            created = True

        if not created:
            preorder_positions = {p.secret: p for p in preorder.positions.all()}
        else:
            preorder_positions = {}

        for position in order['positions']:
            if position['secret'] in preorder_positions:
                pp = preorder_positions[position['secret']]
                del preorder_positions[position['secret']]
            else:
                pp = PreorderPosition(preorder=preorder, secret=position['secret'])

            information = ''
            if questions and 'answers' in position:
                for answer in position['answers']:
                    if answer['question'] in questions:
                        information += (
                            questions[answer['question']]['question']
                            + ' – '
                            + answer['answer']
                            + '\n\n'
                        )

            if not pp.pk:
                pp.information = information
                pp.price = Decimal(position['price'])
                pp.product = product_dict[position['item']]
                to_insert.append(pp)
            elif (
                pp.information != information
                or pp.product_id != product_dict[position['item']].pk
                or str(pp.price) != position['price']
            ):
                pp.price = Decimal(position['price'])
                pp.information = information
                pp.product = product_dict[position['item']]
                pp.save()

        if preorder_positions:
            for pp in preorder_positions.values():
                pp.delete()

        created_orders += int(created)
        loaded_orders += int(not created)

    PreorderPosition.objects.bulk_create(to_insert)
    log.write(
        style.SUCCESS(
            'Found {} new and {} known orders in file.'.format(
                created_orders, loaded_orders
            )
        )
    )

    if add_cashdesks:
        cashdesk_count = add_cashdesks if isinstance(add_cashdesks, int) else 5
        for cashdesk_number in range(cashdesk_count):
            Cashdesk.objects.get_or_create(
                name='Cashdesk {}'.format(cashdesk_number + 1),
                ip_address='127.0.0.{}'.format(cashdesk_number + 1),
            )
        log.write(style.SUCCESS('Added {} cashdesks.'.format(cashdesk_count)))
    log.write(style.SUCCESS('Import done.'))
