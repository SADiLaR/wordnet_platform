A platform for developing WordNets
==================================
A WordNet is a type of lexical database of meanings and relations. See
https://en.wikipedia.org/wiki/WordNet
This platform is a web-based system for the development and maintenance of such
wordnets. It is developed by and for the South African centre for Digital
Language Resources:
https://sadilar.org/

Project goals
=============
The initial need was to support a multilingual wordnet development project: not
merely parallel development of wordnets in different languages, but interlinked
wordnets. The needs of the African wordnet project shaped the initial
priorities. See https://africanwordnet.wordpress.com/

The goal is not to support any and every type of annotation and relation that
can be conceived, but to support the projects through a simple and maintainable
platform that can realistically be self-hosted. With that in mind, simplicity
and maintainability are explicit goals.

Technology
==========
This platform is implemented in Python on the Django web development framework.
A level of familiarity with the Django framework is assumed. Full documentation
is available from here:
https://www.djangoproject.com/

Local development setup
=======================
1. Copy `.env.example` to `.env` in the `wordnet_platform/` directory and fill
   in the values. At minimum you need a `SECRET_KEY` and a `DB_PASSWORD`.

   To generate a secret key:

       python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

2. Start the development server:

       docker compose up

Deployment
==========
A `SECRET_KEY` must be generated and provided as an environment variable before
the application is started. Use the command above to generate one. Do not reuse
the key from your local `.env` file in production.
