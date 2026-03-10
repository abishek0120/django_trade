from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL



class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, name=""):
        if not phone:
            raise ValueError("Phone number is required")

        user = self.model(phone=phone, name=name)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password):
        user = self.create_user(phone=phone, password=password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "phone"

    def __str__(self):
        return self.phone



class Wallet(models.Model): 
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.FloatField(default=10000.0)
    asset_symbol = models.CharField(max_length=20, default="BTCUSDT")
    asset_quantity = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.user} | {self.balance}"


class BotState(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_running = models.BooleanField(default=False)

    candle_limit = models.IntegerField(default=30)
    trade_delay = models.IntegerField(default=10)

    buy_rsi = models.FloatField(default=45)
    sell_rsi = models.FloatField(default=55)

    risk_level = models.CharField(
        max_length=10,
        choices=[("LOW", "LOW"), ("MEDIUM", "MEDIUM"), ("HIGH", "HIGH")],
        default="MEDIUM"
    )



class Transaction(models.Model):
    ACTION_CHOICES = (
        ('BUY', 'BUY'),
        ('SELL', 'SELL'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=4, choices=ACTION_CHOICES)
    price = models.FloatField()
    quantity = models.FloatField()
    balance_before = models.FloatField()
    balance_after = models.FloatField()
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.quantity}"


class BotLog(models.Model):
    LEVEL_CHOICES = (
        ("INFO", "INFO"),
        ("ACTION", "ACTION"),
        ("ERROR", "ERROR"),
    )

    SOURCE_CHOICES = (
        ("BOT", "BOT"),
        ("MANUAL", "MANUAL"),
        ("SYSTEM", "SYSTEM"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
