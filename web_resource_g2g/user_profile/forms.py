from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from django.core.validators import EmailValidator

from .models import WithdrawalRequest


class WithdrawalRequestForm(forms.ModelForm):
    """
    Форма для створення запиту на виведення коштів.
    """
    WITHDRAW_FIXED = 'fixed_15_30'
    WITHDRAW_CUSTOM = 'custom'
    WITHDRAW_NONE = 'do_not_withdraw'

    amount = forms.DecimalField(
        label="Сума виведення ($)",
        required=False,
        max_digits=10,
        decimal_places=2,
        # min_value тепер буде встановлюватися динамічно в clean()
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Наприклад, 100.00',
            'step': '1'
        }),
        # help_text буде оновлюватися динамічно в шаблоні через JavaScript
        help_text=""
    )

    # Оновлені варіанти вибору типу виведення
    WITHDRAW_TYPE_CHOICES = [
        (WITHDRAW_FIXED, '15 і 30 числа кожного місяця (вивести всю суму)'),
        (WITHDRAW_CUSTOM, 'Терміновий вивід (протягом 24 годин)'),
        (WITHDRAW_NONE, 'Не виводити'),
    ]

    withdraw_type = forms.ChoiceField(
        label="Варіанти виведення",
        choices=WITHDRAW_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial=WITHDRAW_FIXED
    )

    payment_method = forms.ChoiceField(
        label="Метод виведення",
        choices=WithdrawalRequest.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='payoneer',
        required=False
    )

    payment_account_info = forms.CharField(
        label="Деталі рахунку (Email Payoneer / Номер картки)",
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Введіть email Payoneer або номер картки'
            }
        )
    )

    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'withdraw_type', 'payment_method', 'payment_account_info']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.DateInput, forms.EmailInput)):
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        withdraw_type = cleaned_data.get('withdraw_type')
        payment_method = cleaned_data.get('payment_method')
        payment_account_info = cleaned_data.get('payment_account_info')

        # Валідація типу виведення
        if withdraw_type not in [choice[0] for choice in self.WITHDRAW_TYPE_CHOICES]:
            raise ValidationError("Зробіть коректний вибір типу виведення")

        # Логіка для "Не виводити": скидаємо всі інші поля
        if withdraw_type == self.WITHDRAW_NONE:
            cleaned_data['amount'] = None
            cleaned_data['payment_method'] = None
            cleaned_data['payment_account_info'] = None
            return cleaned_data

        # Для всіх інших варіантів, payment_method та payment_account_info є обов'язковими
        if not payment_method:
            self.add_error('payment_method', 'Будь ласка, оберіть метод виведення.')

        if not payment_account_info:
            self.add_error('payment_account_info', 'Будь ласка, вкажіть деталі рахунку для виведення.')
        else:
            if payment_method == 'payoneer':
                email_validator = EmailValidator(
                    message='Будь ласка, введіть дійсну адресу електронної пошти Payoneer.')
                try:
                    email_validator(payment_account_info)
                except ValidationError:
                    self.add_error('payment_account_info',
                                   'Будь ласка, введіть дійсну адресу електронної пошти Payoneer.')
            elif payment_method == 'visa_mastercard':
                cleaned_card_number = re.sub(r'\D', '', payment_account_info)
                if not (len(cleaned_card_number) == 16 and cleaned_card_number.isdigit()):
                    self.add_error('payment_account_info',
                                   'Будь ласка, введіть дійсний номер картки Visa/Mastercard (рівно 16 цифр).')

        # Динамічна валідація поля amount:
        # Поле amount є обов'язковим лише для 'custom'
        if withdraw_type == self.WITHDRAW_CUSTOM:
            min_amount_for_method = 0.00 # Значення за замовчуванням
            if payment_method == 'payoneer':
                min_amount_for_method = 50.00
            elif payment_method == 'visa_mastercard':
                min_amount_for_method = 20.00

            if amount is None:
                self.add_error('amount', 'Будь ласка, вкажіть суму виведення.')
            elif amount < min_amount_for_method:
                self.add_error('amount',
                               f'Мінімальна сума виведення для {payment_method.capitalize()} становить ${min_amount_for_method:.2f}.')
        else:
            # Для 'fixed_15_30' (вивести всю суму) amount не потрібний
            cleaned_data['amount'] = None

        return cleaned_data

    def save(self, commit=True, **kwargs):
        instance = super().save(commit=False)

        instance.withdraw_type = self.cleaned_data['withdraw_type']

        if self.cleaned_data.get('payment_account_info'):
            instance.payment_details = {'account_info': self.cleaned_data.get('payment_account_info')}
        else:
            instance.payment_details = None

        if commit:
            instance.save(**kwargs)
        return instance
