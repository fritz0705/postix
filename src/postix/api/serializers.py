from rest_framework import serializers

from postix.core.models import (
    ListConstraint, ListConstraintEntry, Ping, Preorder, PreorderPosition,
    Product, Transaction, TransactionPosition,
)


class PreorderPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreorderPosition
        fields = (
            'id',
            'preorder',
            'secret',
            'product',
            'is_redeemed',
            'is_paid',
            'product_name',
            'pack_list',
            'redemption_message',
        )


class PreorderSerializer(serializers.ModelSerializer):
    positions = PreorderPositionSerializer(many=True, read_only=True)

    class Meta:
        model = Preorder
        fields = ('order_code', 'is_paid', 'is_canceled', 'warning_text', 'positions')


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'price',
            'tax_rate',
            'requires_authorization',
            'is_available',
            'is_availably_by_time',
            'pack_list',
        )


class ListConstraintSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListConstraint
        fields = ('id', 'name')


class ListConstraintEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ListConstraintEntry
        fields = ('id', 'name', 'identifier')


class TransactionPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionPosition
        fields = (
            'id',
            'type',
            'value',
            'tax_rate',
            'tax_value',
            'product',
            'reverses',
            'listentry',
            'preorder_position',
            'items',
            'authorized_by',
        )


class TransactionSerializer(serializers.ModelSerializer):
    positions = TransactionPositionSerializer(many=True, read_only=True)

    class Meta:
        model = Transaction
        fields = ('id', 'datetime', 'session', 'cash_given', 'positions')


class PingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ping
        fields = ('id', 'pinged', 'ponged', 'secret', 'synced')
