# Inline styles only: mail clients ignore <style> blocks. The plain-text part is generated from this HTML.
_STEP = 'style="margin:0 0 14px;padding:2px 0 2px 14px;border-left:3px solid #4f55c7;"'
_NOTE = 'style="margin:22px 0;padding:12px 16px;background:#f3f4fb;border-radius:6px;"'

WELCOME_EMAIL = f"""
<h1 style="margin:0 0 12px;font-size:24px;color:#2b2f77;">Welcome aboard, {{{{ person.first_name }}}}!</h1>

<p>We are glad to have you at Air Sports Live Tracking. Your phone is now your tracker: organisers, crew and spectators can follow
your flight live, and in a competition you are scored as you fly.</p>

<h2 style="margin:22px 0 6px;font-size:16px;color:#2b2f77;">Getting started</h2>

<div {_STEP}><strong>1. Set up the app.</strong> Sign in with the same e-mail you register for events with, and allow location
"all the time" so tracking keeps running with the screen off. The app has a <strong>pre-flight check</strong> that finds
problems (location, battery saver, internet, clock) and fixes them with a tap.
<a href="https://airsports.no/docs/02_Contestant_Guide">Read the pilot guide</a>.</div>

<div {_STEP}><strong>2. Register for an event.</strong> Find it on the <a href="https://airsports.no">mission dashboard</a> or in the app
under "Open for registration today", and press <strong>Register</strong>. You get your flight order automatically, no preparation.
<a href="https://airsports.no/tutorials/#SelfRegistration">Watch the 2-minute tutorial</a>.</div>

<div {_STEP}><strong>3. Fly.</strong> Press play in the app before take-off. Your next flight and its tracking window are on the
home screen, and the app tells you if something stops the positions from reaching us.</div>

<div {_STEP}><strong>Flying in Microsoft Flight Simulator?</strong> The simulator client works the same way, and events say whether
they accept simulator flights.
<a href="https://airsports.no/docs/08_MSFS_Integration">Set it up here</a>.</div>

<div {_STEP}><strong>Want to run your own events?</strong> Press <strong>Become an Organizer</strong> in the top bar of the dashboard.
It is instant, and our <a href="https://airsports.no/docs/12_First_Contest_in_15_Minutes">first contest in 15 minutes</a> guide
takes you from there.</div>

<div {_NOTE}><strong>One thing worth knowing:</strong> some phones (Huawei, OnePlus and others) stop apps in the background to save
battery. If your track freezes, give the app unrestricted battery use.
<a href="https://airsports.no/docs/02_Contestant_Guide#5-troubleshooting-tracking">Here is how</a>.
Tracking is a small annual subscription through the App Store or Google Play.</div>

<p>Questions are always welcome: write to <a href="mailto:support@airsports.no">support@airsports.no</a> or browse the
<a href="https://airsports.no/faq">FAQ</a>. We are happy to run a short webinar for you and your friends if that helps.</p>

<p>Happy flying!</p>
"""

CONTEST_CREATION_EMAIL = f"""
<h1 style="margin:0 0 12px;font-size:24px;color:#2b2f77;">You can now create contests, {{{{ person.first_name }}}}</h1>

<p>Thank you for your interest. Your account is set up to create and manage contests. A computer is the easiest way to work
with routes and tasks. <a href="https://airsports.no/accounts/login/">Log in here</a> with the same e-mail you use in the app
(use "Reset password" if you have not set one).</p>

<p>Tip: build your first contest as a private practice event. Contests are private until you change the visibility, so nobody
sees it before you are ready.</p>

<h2 style="margin:22px 0 6px;font-size:16px;color:#2b2f77;">Five steps to your first event</h2>

<div {_STEP}><strong>1. Create the contest.</strong> <em>My contests &rarr; Create New Contest</em>: name,
dates, time zone and location. A <strong>setup checklist</strong> on the contest page then shows what is left.</div>

<div {_STEP}><strong>2. Draw a route.</strong> <em>Route editor &rarr; Create new route</em>, or
<strong>Import route</strong> from KML, KMZ, GPX or CSV. A route can be reused in many contests.</div>

<div {_STEP}><strong>3. Add a navigation task.</strong> On the contest page press <strong>Add navigation task</strong>, choose the
task type and the route. The first question is <strong>who will fly the task</strong>: real aircraft only (the default),
simulators allowed, or simulator only.</div>

<div {_STEP}><strong>4. Add teams and start times.</strong> Pilots can register themselves from the app or the dashboard
(tick <em>allow self-management</em> on the task), or you add them with <strong>Add team</strong>, <strong>Quick Add</strong> or
<strong>Scheduling</strong>. Flight orders with map and photos are generated for you.</div>

<div {_STEP}><strong>5. Choose who can see it.</strong> In <em>Contest settings &rarr; Publicity</em> choose public or
private. You can keep a task hidden until it goes live.</div>

<div {_NOTE}><strong>Before the flight:</strong> every pilot must be registered with the e-mail they use in the app, and each
flight has a tracking window (start and finish). The contestant list shows who is missing the app. A co-pilot can also run
the app as a backup phone.</div>

<h2 style="margin:22px 0 6px;font-size:16px;color:#2b2f77;">Guides and help</h2>
<ul style="margin:0 0 14px;padding-left:20px;">
    <li><a href="https://airsports.no/docs/12_First_Contest_in_15_Minutes">Your first contest in 15 minutes</a></li>
    <li><a href="https://airsports.no/docs/03_Contest_Manager_Guide">Contest manager guide</a> and
        <a href="https://airsports.no/docs/04_Route_Creation_and_Tasks">route and task guide</a></li>
    <li><a href="https://airsports.no/tutorials/#CreateContest">Video tutorial: create a contest</a></li>
    <li><a href="https://airsports.no/faq">FAQ</a></li>
</ul>

<p>Stuck, or want a second pair of eyes? Write to <a href="mailto:support@airsports.no">support@airsports.no</a>. We are happy to
join a video call and look through your first contest before the first flight.</p>

<p>Good luck with your event!</p>
"""

DELETION_EMAIL = """
<h1 style="margin:0 0 12px;font-size:24px;color:#2b2f77;">Your account has been deleted</h1>

<p>We have removed your Air Sports Live Tracking account and your personal details. Where you appear in the results of a
contest you flew in, your name has been replaced so that the results stay complete.</p>

<p>Thank you for flying with us. If you ever want to come back, install the app and sign up again, it takes a minute.</p>

<p>If you have a moment, we would like to hear what we could have done better:
<a href="mailto:support@airsports.no">support@airsports.no</a>.</p>
"""

SQUADRON_INVITATION_EMAIL = f"""
<h1 style="margin:0 0 12px;font-size:22px;color:#2b2f77;">You are invited to {{{{ squadron }}}}</h1>

<p>{{{{ inviter }}}} has invited you to join the squadron <strong>{{{{ squadron }}}}</strong> at Air Sports Live Tracking{{% if admin %}}, as an admin{{% endif %}}.</p>

{{% if description %}}<div {_NOTE}>{{{{ description }}}}</div>{{% endif %}}

<p>A squadron is a group of people who compete together. When an organiser shares a contest with the squadron, all its
members can see the contest, also when it is private, and register for it.</p>

<p style="margin:22px 0;"><a href="{{{{ url }}}}" style="padding:10px 18px;background:#4f55c7;color:#ffffff;border-radius:6px;text-decoration:none;font-weight:bold;">See the invitation</a></p>

<p>Log in, or create an account, with <strong>this e-mail address</strong> ({{{{ email }}}}): the invitation is waiting for you
on the Squadrons page, where you can accept or decline it. You are not in the squadron until you accept. If you do not know
{{{{ inviter }}}} or do not want this, just ignore the e-mail.</p>
"""

CONTESTANT_STARTED_EMAIL = f"""
<h1 style="margin:0 0 12px;font-size:22px;color:#2b2f77;">{{{{ contestant }}}} has started {{{{ task }}}}</h1>

<p><strong>{{{{ contestant }}}}</strong>{{% if aircraft %}} in {{{{ aircraft }}}}{{% endif %}} has started <strong>{{{{ task }}}}</strong> in
<strong>{{{{ contest }}}}</strong>. Their flight is being tracked and scored now.</p>

<div {_STEP}>Starting point time: <strong>{{{{ start_time }}}}</strong><br>
Tracking window ends: <strong>{{{{ finish_time }}}}</strong></div>

<p style="margin:22px 0;"><a href="{{{{ url }}}}" style="padding:10px 18px;background:#4f55c7;color:#ffffff;border-radius:6px;text-decoration:none;font-weight:bold;">Follow the flight</a></p>

<div {_NOTE}>You get this e-mail because you manage the contest and the task is set to notify its managers when a contestant
starts. Turn it off under <em>Update task details</em> on the task.</div>
"""

CONTESTANT_FINISHED_EMAIL = f"""
<h1 style="margin:0 0 12px;font-size:22px;color:#2b2f77;">{{{{ contestant }}}} has finished {{{{ task }}}}</h1>

<p><strong>{{{{ contestant }}}}</strong>{{% if aircraft %}} in {{{{ aircraft }}}}{{% endif %}} has finished <strong>{{{{ task }}}}</strong> in
<strong>{{{{ contest }}}}</strong>.
{{% if crossed_finish %}}They crossed the finish line.{{% else %}}Their tracking ended without a finish line crossing: the tracking
window ran out or the flight was stopped.{{% endif %}}</p>

<div {_STEP}>Score: <strong>{{{{ score }}}}</strong><br>
State: {{{{ state }}}}</div>

<p>The score is the one calculated from the track. Scores added by hand in the results service, or a recalculation, can still
change it.</p>

<p style="margin:22px 0;"><a href="{{{{ url }}}}" style="padding:10px 18px;background:#4f55c7;color:#ffffff;border-radius:6px;text-decoration:none;font-weight:bold;">See the task</a></p>

<div {_NOTE}>You get this e-mail because you manage the contest and the task is set to notify its managers when a contestant
finishes. Turn it off under <em>Update task details</em> on the task.</div>
"""

FLIGHT_ORDER_EMAIL = f"""
<h1 style="margin:0 0 12px;font-size:22px;color:#2b2f77;">Your flight orders for {{{{ task }}}}</h1>

<p>Hi {{{{ first_name }}}},</p>

<p>Here are the flight orders for <strong>{{{{ task }}}}</strong> in <strong>{{{{ contest }}}}</strong>.</p>

<div {_STEP}>Starting point time: <strong>{{{{ start_time }}}}</strong> ({{{{ time_kind }}}}){{% if adaptive %}}<br>
Adaptive start: you choose your start in the app, no earlier than {{{{ tracking_start }}}}{{% endif %}}<br>
Tracking window opens: <strong>{{{{ tracking_start }}}}</strong></div>

<p style="margin:20px 0;"><a href="{{{{ url }}}}" style="display:inline-block;padding:12px 22px;background:#4f55c7;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Open your flight orders</a></p>

<div {_NOTE}><strong>On the day:</strong> open the app, run the pre-flight check and press play before take-off. Positions are
scored inside your tracking window, so start tracking while you are still on the ground. If something is wrong, the app tells
you.</div>

<p>Have a great flight!</p>
"""

EMAIL_SIGNATURE = """
<p style="margin-top:28px;padding-top:14px;border-top:1px solid #e3e5f0;"><strong>Team Air Sports Live Tracking</strong><br>
<a href="https://airsports.no">airsports.no</a> &middot; <a href="https://airsports.no/faq">FAQ</a> &middot;
<a href="mailto:support@airsports.no">support@airsports.no</a><br>
<a href="https://apps.apple.com/no/app/air-sports-live-tracking/id1559193686">App Store</a> &middot;
<a href="https://play.google.com/store/apps/details?id=no.airsports.android.livetracking">Google Play</a> &middot;
<a href="https://www.youtube.com/@AirSportsLiveTracking">YouTube</a></p>
<p style="font-size:12px;color:#6b6f85;">Air Sports Live Tracking is a non-profit organisation run on voluntary work.</p>
"""

PLAIN_SIGNATURE = """
--
Team Air Sports Live Tracking
https://airsports.no  |  FAQ: https://airsports.no/faq  |  support@airsports.no
App Store: https://apps.apple.com/no/app/air-sports-live-tracking/id1559193686
Google Play: https://play.google.com/store/apps/details?id=no.airsports.android.livetracking
Air Sports Live Tracking is a non-profit organisation run on voluntary work.
"""
