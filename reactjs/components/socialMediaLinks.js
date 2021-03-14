import React, {Component} from "react";
import {mdiFacebook, mdiInstagram, mdiMagnify, mdiMail, mdiTwitter, mdiYoutube} from "@mdi/js";
import Icon from "@mdi/react";

export class SocialMediaLinks extends Component {
    render() {
        return <div className={"social-media-box"}>
            <a href={"https://www.instagram.com/AirSportsLive"}><Icon path={mdiInstagram} title={"Instagram"} size={1.1}
                                                                      color={"black"}/></a>
            <a href={"https://www.twitter.com/AirSportsLive"}><Icon path={mdiTwitter} title={"Twitter"} size={1.1}
                                                                    color={"black"}/></a>
            <a href={"https://www.facebook.com/AirSportsLive"}><Icon path={mdiFacebook} title={"Facebook"} size={1.1}
                                                                     color={"black"}/></a>
            <a href={"https://www.youtube.com/channel/UCgKCfAzU9wl42wnb1Tj_SCA"}><Icon path={mdiYoutube}
                                                                                       title={"Youtube"} size={1.1}
                                                                                       color={"black"}/></a>
            <a href={"mailto:support@airsports.no"}><Icon path={mdiMail} title={"E-mail"} size={1.1}
                                                          color={"black"}/></a>

        </div>
    }
}