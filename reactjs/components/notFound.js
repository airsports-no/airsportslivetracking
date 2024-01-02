import { Link } from "react-router-dom";
import React from "react";

export default function NotFound() {
    return (
        <div>
            <h1>Oops! You seem to be lost.</h1>
            <p>Here are some helpful links:</p>
            <Link to='/'>Home</Link><br/>
            <Link to='https://home.airsports.no/faq/'>FAQ</Link>
        </div>
    )
}