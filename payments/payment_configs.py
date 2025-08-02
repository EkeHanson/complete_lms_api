# Default payment gateway configurations for test and live modes
PAYMENT_GATEWAY_CONFIGS = [
    {
        'name': 'Paystack',
        'description': 'Paystack payment gateway for African markets',
        'is_active': True,
        'is_test_mode': True,
        'is_default': True,
        'config': {
            'test_api_key': 'sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_api_key': 'sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'webhook_url': 'https://yourapp.com/paystack/webhook',
            'currency': 'NGN'
        }
    },
    {
        'name': 'Paypal',
        'description': 'PayPal payment gateway for global transactions',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_client_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'test_client_secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_client_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_client_secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'sandbox_url': 'https://api.sandbox.paypal.com',
            'live_url': 'https://api.paypal.com'
        }
    },
    {
        'name': 'Stripe',
        'description': 'Stripe payment gateway for global transactions',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_publishable_key': 'pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'test_secret_key': 'sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_publishable_key': 'pk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_secret_key': 'sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'webhook_secret': 'whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }
    },
    {
        'name': 'Flutterwave',
        'description': 'Flutterwave payment gateway for African markets',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_public_key': 'FLWPUBK_TEST-xxxxxxxxxxxxxxxxxxxxxxxx-X',
            'test_secret_key': 'FLWSECK_TEST-xxxxxxxxxxxxxxxxxxxxxxxx-X',
            'live_public_key': 'FLWPUBK-xxxxxxxxxxxxxxxxxxxxxxxx-X',
            'live_secret_key': 'FLWSECK-xxxxxxxxxxxxxxxxxxxxxxxx-X',
            'encryption_key': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }
    },
    {
        'name': 'Remita',
        'description': 'Remita payment gateway for Nigerian markets',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_merchant_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'test_api_key': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_merchant_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_api_key': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'service_type_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }
    },
    {
        'name': 'Interswitch',
        'description': 'Interswitch payment gateway for African markets',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_client_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'test_client_secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_client_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_client_secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'merchant_code': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }
    },
    {
        'name': 'Monnify',
        'description': 'Monnify payment gateway for Nigerian markets',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_api_key': 'MK_TEST_xxxxxxxxxxxxxxxxxxxxxxxx',
            'test_contract_code': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_api_key': 'MK_PROD_xxxxxxxxxxxxxxxxxxxxxxxx',
            'live_contract_code': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }
    },
    {
        'name': 'Square',
        'description': 'Square payment gateway for global transactions',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'test_access_token': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'test_application_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_access_token': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_application_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'location_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        }
    },
    {
        'name': 'ApplePay',
        'description': 'Apple Pay payment gateway for mobile transactions',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'merchant_id': 'merchant.com.yourapp',
            'test_payment_token': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_payment_token': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'domain_name': 'yourapp.com'
        }
    },
    {
        'name': 'GooglePay',
        'description': 'Google Pay payment gateway for mobile transactions',
        'is_active': False,
        'is_test_mode': True,
        'is_default': False,
        'config': {
            'merchant_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'test_gateway_token': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'live_gateway_token': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'merchant_name': 'Your App Name'
        }
    }
]