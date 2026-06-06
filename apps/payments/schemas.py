from ninja import Schema


class PaymentTypeOut(Schema):
    value: str
    label: str
