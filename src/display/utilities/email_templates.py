WELCOME_EMAIL = """
<p>Dear {{ person.first_name }} {{ person.last_name }}</p>

<p><strong>Welcome to Air Sports Live Tracking</strong><br>
Thank you for downloading the Air Sports Live Tracking APP and being part of the Air Sports Live Tracking Team. We hope you enjoy it.</p>
  
<p><strong>With Air Sports Live Tracking you can:</strong></p>
<ol>
    <li>Maximize the use of the Live Tracking app. Read our guide for useful tips on installing and using the App. <a href="https://home.airsports.no/docs/02_Contestant_Guide"><strong>– Installation Guide –</strong></a></li>
    <li>Register yourself for a competition and receive an automatically generated Flight Order. No preparation, just go flying! Find the event on the global map and click: “Manage Crew” to attend. <a href="https://home.airsports.no/tutorials/#SelfRegistration">Watch this Self-Register tutorial</a>.</li>
    <li>Become a Contest Administrator and create your own competitions. Get access to create contests for yourself and your club. This is provided by sending an application email to Team Air Sports administration at <a href="mailto:support@airsports.no">support@airsports.no</a></li>
</ol>
  
<p>For more info visit our <strong>News & FAQ</strong>: <a href="https://home.airsports.no/faq">home.airsports.no/faq</a> or see our tutorials on <a href="https://www.youtube.com/c/AirSportsLiveTracking?sub_confirmation=1">YouTube</a>, and please subscribe.</p>

<p><strong>IMPORTANT:</strong><br>
<strong>Access to position</strong> : The app requires access to position even when the APP is in the background. This is especially important in a competition.<br>
<strong>Huawei/OnePlus</strong> : We have experienced that some phones do not provide access to the battery when the app is in the background. Smartphone owners must therefore check, and go into the settings and manually give the APP access to the battery when the app is in the background mode. <a href="https://home.airsports.no/docs/02_Contestant_Guide#4-troubleshooting-tracking"><strong>Please read the guide for crucial settings and helpful tips!</strong></a></p>

<p>Read more about Air Sports Live Tracking; <a href="https://home.airsports.no">home.airsports.no</a>.</p>
  
<p>We wish you all the best and let us know if you have any questions. If you want, we can arrange a webinar for you and your friends, to show some of the most important features.</p>
"""

CONTEST_CREATION_EMAIL = """
<p>Dear {{ person.first_name }} {{ person.last_name }}</p>

<p>Thank you for your inquiry. You now have the access to create contests.<br>
To create contests etc, we recommend the use of a computer for best results.</p>
  
<p>If you have not logged in to <a href="http://airsports.no/">airsports.no</a> webpage, you can access this by requesting a first-time password by pressing the gear icon in the menu. (PS. this does not affect your access via the app, but it is important that you use the same email, this is linked to your profile.) <a href="https://www.airsports.no/accounts/login/">log in</a></p>

<p>To make a competition is not difficult, but the complexity of a competition gives you some choices.</p>
  
<p><strong>THE PRINCIPLE IS SIMPLE.</strong></p>
<ol>
    <li><strong>Create a contest.</strong> The dates control visibility on the global map etc. You can also choose whether it should be private (only visible to you) or open to everyone. Share administration rights with others if you have their email and they have access to creator mode. You have the option to make competitions public, while keeping the tasks closed until it goes live. Please make sure to follow us on <a href="https://www.youtube.com/@AirSportsLiveTracking">YouTube</a>, and stay up-to-date with our latest updates!</li>
    <li><strong>Add participants</strong> to the competition itself. The easiest way to do this is to get the participants to do it themselves, through the app. Alternatively, you can do it manually. Watch this <a href="https://home.airsports.no/tutorials/#SelfRegistration">tutorial for self registration</a>, or send it to your participants. Note: It is mandatory for all participants to download the APP in order to create a profile.</li>
    <li><strong>Task</strong>. For a competition, one or more tasks are created. The task can be created in our <strong>new “Route editor”</strong>. You will find it on the top menu “Contest management” -> “Route editor”. Remember to save your route. When the route is finished you can assign it to a competition or make a new. Please watch this <a href="https://home.airsports.no/tutorials/#CreateContest">step-by-step tutorial on <strong>Contest Management</strong></a> or read our <a href="https://home.airsports.no/docs/04_Route_Creation_and_Tasks"><strong>Route Creation Guide</strong></a>.</li>
</ol>
  
<p>Once the participants are registered in the competition, it is easy to add them to a task. This can be done via the “Auto schedule”, or if it is an informal competition, the participants can also register themselves at the start (self-schedule-flight). With Self-Schedule the participant automatically receives a “flight order” by email with map and photos.</p>

<p><strong>IMPORTANT</strong> : Each participant is assigned a tracker time in the registration. (Start-end) It is important that the flight takes place within this time frame. The administrator can control this time frame directly in “Tracker start time” / “Finished by time” or add extra time in “minutes to landing” in the task if there is no landing gate.</p>
  
<p><strong>THE USE OF FLIGHT CONTEST.</strong><br>
If you use a Flight Contest (FC), it is important that the competition has the same name. The easiest way is to enter the participants in Air Sports, and then export them to the Flight Contest. When this is done, you finish everything in FC and export this back to Air Sports Live Tracking.</p>
  
<p><strong>IN THE GREEN ●</strong><br>
Before flying, remember to check so the participants register with the same email they are using in the app. We have added a “light-signal icon” that shows if the app is active, or if the participant is missing the app. This is green if the participant turns on tracking and is registered correctly.</p>
  
<p><strong>HELP – Do not hesitate to contact us</strong> if you have any questions. If there are more who are interested in access (for example to for training) then we can arrange that. We can also do a skype or MS Teams meeting to explain more. Once you have created your first competition, if you want, we can do an overview to see that everything is in order before you make your flight. Just let us know. Please visit <a href="https://home.airsports.no/faq"><strong>home.airsports.no/faq</strong></a>, here you will find <strong>News, Tutorials, FAQ</strong>, <strong>Webinars</strong> and other <strong>helpful information</strong>.</p>
  
<p>Good luck!</p>
"""

DELETION_EMAIL = """
<p>Hi.</p>

<p>Your profile has now been deleted, but we welcome you back at any time.</p>

<p>Air Sports Live Tracking is currently at an early stage of the development. We are constantly working to improve the platform. If you have any feedback or suggestions, please let us know.</p>
"""

EMAIL_SIGNATURE = """
<p>–</p>
<p><strong>Team Air Sports Live Tracking</strong><br>
<a href="https://home.airsports.no">home.airsports.no</a></p>
"""
