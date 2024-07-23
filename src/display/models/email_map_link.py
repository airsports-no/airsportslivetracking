import logging
import uuid

from django.core.mail import send_mail
from django.db import models
from django.templatetags.static import static
from django.urls import reverse

logger = logging.getLogger(__name__)


class EmailMapLink(models.Model):
    """
    Contains a generated flight order for a contestant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    orders = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    HTML_SIGNATURE = f"""
<h3><strong>Best Regards,</strong><br /><span style="color: #000080;">
<strong>Team&nbsp;Air Sports Live Tracking</strong>
<strong>&nbsp;</strong>
</span></h3>
<p>Flight Tracking and competition flying made easy!&nbsp;<br /> <br /> 
<em>Air Sports Live Tracking gives you live tracking and live scoring of competitions in Precision Flying and Air 
Navigation Racing. GA pilot? We also provide an open GA flight tracking service. Using your mobile as a tracker you 
can follow it live on&nbsp;</em><em><a href="http://www.airsports.no/" data-saferedirecturl="https://www.google.com/url?q=http://www.airsports.no/&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNGxwqYMGGRw9YV110LVORQjwrEKSg">www.airsports.no</a></em><em>.</em></p>

<p><em>Download APP:&nbsp;&nbsp;</em><em><a href="https://apps.apple.com/no/app/air-sports-live-tracking/id1559193686?l=nb" data-saferedirecturl="https://www.google.com/url?q=https://apps.apple.com/no/app/air-sports-live-tracking/id1559193686?l%3Dnb&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNEaGuuRKna3cTbq1d9pFS5W0XjhHg">Apple Store</a></em><em>&nbsp;|&nbsp;</em><em><a href="https://play.google.com/store/apps/details?id=no.airsports.android.livetracking" data-saferedirecturl="https://www.google.com/url?q=https://play.google.com/store/apps/details?id%3Dno.airsports.android.livetracking&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNGm5zuqA1ARkWWhBHJFCMoEHOEITQ">Google Play</a></em><br /> <br /> Follow us:&nbsp;<a href="https://www.instagram.com/AirSportsLive" data-saferedirecturl="https://www.google.com/url?q=https://www.instagram.com/AirSportsLive&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNHQAv3QL2PQFDIv8jmTQj6QVXNDng">Instagram</a>&nbsp;|&nbsp;&nbsp;<a href="https://twitter.com/AirSportsLive" data-saferedirecturl="https://www.google.com/url?q=https://twitter.com/AirSportsLive&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNFgfCQfnysD__aABYrpmxbmDh36EQ">Twitter</a>&nbsp; |&nbsp;&nbsp;<a href="https://www.facebook.com/AirSportsLive" data-saferedirecturl="https://www.google.com/url?q=https://www.facebook.com/AirSportsLive&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNHYjyR8NJqLEAtt7acO6jaJCF7Suw">Facebook</a>&nbsp; |&nbsp;&nbsp;<a href="https://www.youtube.com/channel/UCgKCfAzU9wl42wnb1Tj_SCA" data-saferedirecturl="https://www.google.com/url?q=https://www.youtube.com/channel/UCgKCfAzU9wl42wnb1Tj_SCA&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNHx8Xk2Xlrp6S9RRedRguMFi2Gi7w">YouTube</a><br /> <br /> <span style="color: #ff0000;"><strong>Partners:&nbsp;</strong></span><br /> <strong>Norges Luftsportforbund /&nbsp;<em>Norwegian Air Sports Federation&nbsp;</em></strong><strong><a href="https://nlf.no/" data-saferedirecturl="https://www.google.com/url?q=https://nlf.no/&amp;source=gmail&amp;ust=1630044200327000&amp;usg=AFQjCNH_cLc2E8CUYMNJH9lDgRKxaAQksw">&gt;&gt;</a></strong><br /> <strong>IG - TRADE WITH IG&nbsp;</strong><strong><a href="https://www.ig.com/no/demokonto/?CHID=15&amp;QPID=35652" data-saferedirecturl="https://www.google.com/url?q=https://www.ig.com/no/demokonto/?CHID%3D15%26QPID%3D35652&amp;source=gmail&amp;ust=1630044200328000&amp;usg=AFQjCNET2W7jI_hyJLIFfL986LWWgdaA7g">&gt;&gt;</a></strong></p>

<p><br /> <em>Air Sports Live Tracking is based on voluntary work and is a non-profit organization.&nbsp;We depend on 
partners who support our work.&nbsp;If you want to become our partners, please get in touch, we are very grateful for 
your support.&nbsp;Thanks!</em></p>

<p><em><img src="{static("img/AirSportsLiveTracking.png")}" alt="Air Sports Live Tracking" width="350" height="52" /></em></p>
<p><span style="color: #999999;">____________________________________________________________</span></p>
<p><span style="color: #999999;"><em>NOTICE: This e-mail transmission, and any documents, files or previous e-mail 
messages attached to it, may contain confidential or privileged information. If you are not the intended recipient, or 
a person responsible for delivering it to the intended recipient, you are hereby notified that any disclosure, copying, 
distribution or use of any of the information contained in or attached to this message is STRICTLY PROHIBITED. If you 
have received this transmission in error, please immediately notify the sender and delete the e-mail and attached 
documents. Thank you.</em></span></p>
<p><span style="color: #999999;">____________________________________________________________</span></p>"""

    PLAINTEXT_SIGNATURE = """Best Regards,
Team Air Sports Live Tracking 
Flight Tracking and competition flying made easy! 

Air Sports Live Tracking gives you live tracking and live scoring of competitions in Precision Flying and Air Navigation 
Racing. GA pilot? We also provide an open GA flight tracking service. Using your mobile as a tracker you can follow it 
live on www.airsports.no.

Download the APP from:
Apple Store (https://apps.apple.com/no/app/air-sports-live-tracking/id1559193686?l=nb)
Google Play (https://play.google.com/store/apps/details?id=no.airsports.android.livetracking)

Follow us: 
Instagram (https://www.instagram.com/AirSportsLive)
Twitter (https://twitter.com/AirSportsLive)
Facebook (https://www.facebook.com/AirSportsLive)
YouTube (https://www.youtube.com/channel/UCgKCfAzU9wl42wnb1Tj_SCA)

Partners: 
Norges Luftsportforbund / Norwegian Air Sports Federation (https://nlf.no/)
IG - TRADE WITH IG (https://www.ig.com/no/demokonto/?CHID=15&QPID=35652)

Air Sports Live Tracking is based on voluntary work and is a non-profit organization. We depend on partners who support 
our work. If you want to become our partners, please get in touch, we need your  support. Thanks!
____________________________________________________________
 NOTICE: This e-mail transmission, and any documents, files or previous e-mail messages attached to it, may contain 
 confidential or privileged information. If you are not the intended recipient, or a person responsible for delivering 
 it to the intended recipient, you are hereby notified that any disclosure, copying, distribution or use of any of the 
 information contained in or attached to this message is STRICTLY PROHIBITED. If you have received this transmission in 
 error, please immediately notify the sender and delete the e-mail and attached documents. Thank you.
____________________________________________________________    
"""

    def __str__(self):
        return str(self.contestant) + " " + str(self.contestant.navigation_task)

    def send_email(self, email_address: str, first_name: str):
        """
        Sends an e-mail to a contestant with a link to the flight order.
        """
        logger.info(f"Sending email to {email_address}")
        url = "https://airsports.no" + reverse("email_map_link", kwargs={"key": self.id})

        starting_point_time_string = self.contestant.starting_point_time_local.strftime("%Y-%m-%d %H:%M:%S")
        tracking_start_time_string = self.contestant.tracker_start_time_local.strftime("%Y-%m-%d %H:%M:%S")
        send_mail(
            f"Flight orders for task {self.contestant.navigation_task.name}",
            f"Hi {first_name},\n\nHere is the <a href='{url}'>link to download the flight orders</a> for your navigation task "
            + f"'{self.contestant.navigation_task.name}' with {'estimated' if self.contestant.adaptive_start else 'exact'} starting point time {starting_point_time_string} "
            f"{f'and adaptive start (with earliest takeoff time {tracking_start_time_string})' if self.contestant.adaptive_start else ''}.\n\n{url}\n{self.PLAINTEXT_SIGNATURE}",
            None,  # Should default to system from email
            recipient_list=[email_address],
            html_message=f"Hi {first_name},<p>Here is the link to download the flight orders for  "
            f"your navigation task "
            f"'{self.contestant.navigation_task.name}' with {'estimated' if self.contestant.adaptive_start else 'exact'} starting point time {starting_point_time_string} "
            f"{f'and adaptive start (with earliest takeoff time {tracking_start_time_string})' if self.contestant.adaptive_start else ''}.<p>"
            f"<a href='{url}'>Flight orders link</a><p>{self.HTML_SIGNATURE}",
        )
