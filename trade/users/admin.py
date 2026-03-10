from django.contrib import admin
from .models import User, Wallet, BotState, Transaction

#admin.site.register(User)
admin.site.register(Wallet)
admin.site.register(BotState)
admin.site.register(Transaction)