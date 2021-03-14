import React, {Component} from "react";
import {SocialMediaIconsReact} from 'social-media-icons-react';

export class SocialMediaLinks extends Component {
    render() {
        return <div className={"social-media-box"}>
            <SocialMediaIconsReact borderColor="rgba(0,0,0,0.25)" borderWidth="5" borderStyle="solid" icon="instagram"
                                   iconColor="rgba(255,255,255,1)" backgroundColor="rgba(223,27,27,1)" iconSize="5"
                                   roundness="20%" url="https://www.instagram.com/AirSportsLive" size="100"/>
            <SocialMediaIconsReact borderColor="rgba(0,0,0,0.25)" borderWidth="5" borderStyle="solid" icon="twitter"
                                   iconColor="rgba(255,255,255,1)" backgroundColor="rgba(223,27,27,1)" iconSize="5"
                                   roundness="20%" url="https://twitter.com/AirSportsLive" size="100"/>
            <SocialMediaIconsReact borderColor="rgba(0,0,0,0.25)" borderWidth="5" borderStyle="solid" icon="facebook"
                                   iconColor="rgba(255,255,255,1)" backgroundColor="rgba(223,27,27,1)" iconSize="5"
                                   roundness="20%" url="https://www.facebook.com/AirSportsLive" size="100"/>
            <SocialMediaIconsReact borderColor="rgba(0,0,0,0.25)" borderWidth="5" borderStyle="solid" icon="youtube"
                                   iconColor="rgba(255,255,255,1)" backgroundColor="rgba(223,27,27,1)" iconSize="5"
                                   roundness="20%" url="https://www.youtube.com/channel/UCgKCfAzU9wl42wnb1Tj_SCA"
                                   size="100"/>
            <SocialMediaIconsReact borderColor="rgba(0,0,0,0.25)" borderWidth="5" borderStyle="solid" icon="mail"
                                   iconColor="rgba(255,255,255,1)" backgroundColor="rgba(223,27,27,1)" iconSize="5"
                                   roundness="20%" url="support@airsports.no" size="100"/>
        </div>
    }
}