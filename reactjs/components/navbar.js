import React from "react";

export default function Navbar(props) {
    return <nav className="navbar transparent navbar-light">
        <a className="navbar-brand" href="/"><img style={{height: "30px"}}
                                                  src={document.configuration.STATIC_FILE_LOCATION+"img/AirSportsLiveTracking.png"}
                                                  alt="AirSports"/></a>

    </nav>
}