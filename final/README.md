# NameSprouts application

This folder contains the Flask application. See the repository README for the customer flow, setup instructions, and Stripe configuration.

On Windows, create a virtual environment, install requirements.txt, copy .env.example to .env, and run:

    py -m flask --app app run --debug

The default database is created in instance/ and the default one-time price is $5 USD. Stripe checkout remains disabled until test credentials are configured.

