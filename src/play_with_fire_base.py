from typing import Optional, Dict

from firebase_admin.messaging import Message, Notification, FCMOptions, AndroidConfig

# from display.models import MyUser
#
# user = MyUser.objects.get(email="frankose@ifi.uio.no")
# print(user.firebase_user.first().uid)
# # ie9useSHy6gnc2qXlwLiS8oyMrK2
# print(MyUser.objects.get(email="espengronstad@gmail.com").firebase_user.first().uid)
# # 2ckJmjFeA1fNt96pDsy7h8U0IHm2
import firebase_admin
from firebase_admin import credentials, messaging

frank = "ie9useSHy6gnc2qXlwLiS8oyMrK2"
espen = "2ckJmjFeA1fNt96pDsy7h8U0IHm2"
cred = credentials.Certificate("/config/firebase-admin.json")
firebase_admin.initialize_app(cred)


def send_message(
    data: Optional[Dict[str, str]] = None,
    notification: Optional[Notification] = None,
    token: Optional[str] = None,
    fcm_options: Optional[FCMOptions] = None,
    android_config: Optional[AndroidConfig] = None,
    dry_run: bool = False,
) -> str:
    if not data and not notification and not (android_config and android_config.data):
        raise ValueError("No data or message to send")
    message: Message = Message(
        data=data,
        notification=notification,
        token=token,
        fcm_options=fcm_options,
        android=android_config,
    )
    return messaging.send(message, dry_run=dry_run)  # return message ID


message_id = send_message(
    token=frank, notification=Notification(title="My first notification", body="Everything is fine")
)
print(f"Message sent: {message_id}")
