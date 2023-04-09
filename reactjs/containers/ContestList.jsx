import React from "react";
import {createRoot} from "react-dom/client";
import {ContestList} from "../components/contests/contestList";

const root = createRoot(document.getElementById("root"))

root.render(<ContestList/>)
