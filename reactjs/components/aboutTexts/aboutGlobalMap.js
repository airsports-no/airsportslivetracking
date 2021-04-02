import React, {Component} from "react";

const aboutGlobalMap = <div>
    <img src={"/static/img/airsports_no_text.png"} style={{float: "right", width: "50px"}} alt={"Global logo"}/>
    <h2>Global map</h2><br/>
    <p>
        The global map shows an overview of ongoing and upcoming events, as well as all traffic currently using the
        tracking platform. By clicking on individual events the user can jump to the event details on the map and also
        to the competition tracking pages if they exist.
    </p>
    <p>
        The map is for entertainment use only, but we strive to keep the positions up-to-date for all the users who are
        actively tracking their aircraft position.
    </p>
    <p/>
    Take part in tracking your flights or competing in contests by downloading the Air Sports Live Tracking app
    from Google Play or Apple App Store.
    <div className={"d-flex justify-content-around"}>
        <div className={"p-2"}>
        <a
           href='https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1'><img
            alt='Get it on Google Play' style={{height: "60px"}}
            src='https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png'/></a>
        </div>
        <div className={"p-2"}>
        <a
           href="https://apps.apple.com/us/app/pinpong-1-2-players/id1015819050?itsct=apps_box&amp;itscg=30200"><img style={{height: "60px", padding:"8px"}}
                                                                                            src="https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us??size=500x166&amp;releaseDate=1436918400&h=a41916586b4763422c974414dc18bad0"
                                                                                            alt="Download on the App Store"/></a>
        </div>
    </div>
</div>

export default aboutGlobalMap
