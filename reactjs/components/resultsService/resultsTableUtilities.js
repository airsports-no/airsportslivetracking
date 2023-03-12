import Icon from "@mdi/react";
import {mdiChevronDown, mdiChevronUp} from "@mdi/js";
import React from "react";

export function sortFunc(a, b, order, dataField, rowA, rowB) {
    if (b === '-') return -1
    if (a === '-') return 1
    if (order === 'asc') {
        return a - b;
    }
    return b - a; // desc
}

export function sortCaret(order, column) {
    const up = <Icon path={mdiChevronUp} title={"Ascending"} size={1}/>
    const down = <Icon path={mdiChevronDown} title={"Descending"} size={1}/>

    if (!order) return null;
    else if (order === 'asc') return up;
    else if (order === 'desc') return down;
    return null;
}
