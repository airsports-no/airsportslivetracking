import React, {Component} from "react";

export default function Navbar(props) {
    return <nav className="navbar navbar-expand-lg navbar-dark bg-dark">
        <a className="navbar-brand" href="/">Airsports</a>
        <button className="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarSupportedContent"
                aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
            <span className="navbar-toggler-icon"></span>
        </button>

        <div className="collapse navbar-collapse" id="navbarSupportedContent">
            <ul className="navbar-nav mr-auto">
                <li className="nav-item">
                    <a target="_blank" className="nav-link" href="https://youtu.be/4ZPlDVjXabs">Tutorial</a>
                </li>
                <li className="nav-item">
                    <a className="nav-link" href="/resultsservice/">Results service</a>
                </li>
            </ul>
            <ul className="navbar-nav ml-auto">

            </ul>

        </div>
    </nav>
}