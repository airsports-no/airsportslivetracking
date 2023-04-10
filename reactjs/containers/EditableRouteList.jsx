import React from "react";
import {createRoot} from "react-dom/client";
import {EditableRouteList} from "../components/routeEditor/editableRouteList";

const root = createRoot(document.getElementById("root"))

root.render(<EditableRouteList/>)
