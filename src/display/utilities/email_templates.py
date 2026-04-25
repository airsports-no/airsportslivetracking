WELCOME_EMAIL = """
<p>Dear {{ person.first_name }} {{ person.last_name }}</p>

<p><strong>Welcome to Air Sports Live Tracking</strong><br>
Thank you for downloading the Air Sports Live Tracking APP and being part of the Air Sports Live Tracking Team. We hope you enjoy it.</p>
  
<p><strong>With Air Sports Live Tracking you can:</strong></p>
<ol>
    <li>Maximize the use of the Live Tracking app. Read our guide for useful tips on installing and using the App. <a href="https://home.airsports.no/docs/02_Contestant_Guide"><strong>– Installation Guide –</strong></a></li>
    <li>Register yourself for a competition and receive an automatically generated Flight Order. No preparation, just go flying! Find the event on the mission dashboard and click: “Register” to attend. <a href="https://home.airsports.no/tutorials/#SelfRegistration">Watch this Self-Register tutorial</a>.</li>
    <li>Become a Contest Administrator and create your own competitions. To get started, go to your <a href="https://airsports.no">Mission Dashboard</a> and click the <strong>"Become Organizer"</strong> button in the top menu. This will instantly grant you the privileges needed to host and manage your own events.</li>
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

<p>Thank you for your inquiry. You now have access to create and manage contests.<br>
To create contests and design routes, we recommend using a computer for the best experience.</p>
  
<p>If you have not logged in to the <a href="https://airsports.no/">airsports.no</a> dashboard, you can access it by using your registered email. If you need a password, you can request one via the login page. <a href="https://airsports.no/accounts/login/">Log in here</a></p>

<p>Setting up a competition is straightforward. Follow this flow to get your first event live:</p>
  
<p><strong>THE ORGANIZER FLOW:</strong></p>
<ol>
    <li><strong>Create a Contest</strong>: Click the <strong>"Create New Contest"</strong> button in the top right corner of your Mission Dashboard. This establishes the overall event, its dates, and location.</li>
    <li><strong>Manage Contest</strong>: After creating your contest, click the <strong>"Manage"</strong> button on the contest card to enter the administrative area.</li>
    <li><strong>Create a Route</strong>: Before you can track pilots, you need a <strong>Route</strong> (the geometric building blocks like gates and corridors). Inside Contest Management, click <strong>"Create Your First Route"</strong> or use the "Route Management" link in the top menu.</li>
    <li><strong>Establish Tasks</strong>: Once your route is saved, you can create a <strong>Navigation Task</strong> (a specific competition instance). You can do this by clicking <strong>"Add New Navigation Task"</strong> inside your Contest Management page, or by clicking <strong>"Create Task from Route"</strong> directly from your list of saved routes.</li>
    <li><strong>Custom Background Maps</strong>: You can also upload your own georeferenced background maps (aeronautical charts or custom imagery) to be used for both the live competition map and printed flight orders. Manage your uploads via the <strong>"My Maps"</strong> link in the top menu.</li>
</ol>
  
<p>Once your tasks are created, participants can register themselves through the dashboard or app. You can then use the <strong>"Auto Schedule"</strong> feature to assign takeoff times and generate flight orders automatically.</p>

<p><strong>RESOURCES:</strong></p>
<ul>
    <li><a href="https://home.airsports.no/docs/04_Route_Creation_and_Tasks"><strong>Route Creation & Task Guide</strong></a></li>
    <li><a href="https://home.airsports.no/tutorials/#CreateContest"><strong>Step-by-step Video Tutorials</strong></a></li>
    <li><a href="https://www.youtube.com/@AirSportsLiveTracking"><strong>YouTube Channel</strong></a></li>
</ul>

<p><strong>HELP – Do not hesitate to contact us</strong> if you have any questions. We can arrange Skype or MS Teams meetings to show you the ropes, or review your first contest setup to ensure everything is in order before the first flight. Visit <a href="https://home.airsports.no/faq"><strong>home.airsports.no/faq</strong></a> for more helpful information.</p>
  
<p>Good luck with your event!</p>
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
