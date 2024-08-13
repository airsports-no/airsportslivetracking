import React, { CSSProperties, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import moment from 'moment';
var momentDurationFormatSetup = require("moment-duration-format");

import {
  ColumnDef,
  Row,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'

// needed for table body level scope DnD setup
import {
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { restrictToVerticalAxis } from '@dnd-kit/modifiers'
import {
  arrayMove,
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'

// needed for row & cell level scope DnD setup
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

// Cell Component
const RowDragHandleCell = ({ rowId }) => {
  const { attributes, listeners } = useSortable({
    id: rowId,
  })
  return (
    // Alternatively, you could set these attributes on the rows themselves
    <button {...attributes} {...listeners}>
      🟰
    </button>
  )
}

// Row Component
const DraggableRow = ({ row, className }) => {
  const { transform, transition, setNodeRef, isDragging } = useSortable({
    id: row.original.waypoint_name,
  })

  const style = {
    transform: CSS.Transform.toString(transform), //let dnd-kit do its thing
    transition: transition,
    opacity: isDragging ? 0.8 : 1,
    zIndex: isDragging ? 1 : 0,
    position: 'relative',
  }
  return (
    // connect row ref to dnd-kit, apply important styles
    <tr ref={setNodeRef} style={style} className={className}>
      {row.getVisibleCells().map(cell => (
        <td key={cell.id} style={{ width: cell.column.getSize() }}>
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </td>
      ))}
    </tr>
  )
}

function getCookie() {
  const name = 'csrftoken'
  var cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var cookie = jQuery.trim(cookies[i]);
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function groupByGate(items) {
  return items.reduce((acc, item) => {
    // If the gate key does not exist in the accumulator, create it and set it to an empty array
    if (!acc[item.gate]) {
      acc[item.gate] = [];
    }
    // Push the current item into the gate array
    acc[item.gate].push(item);
    return acc;
  }, {}); // Initial value is an empty object
}

const LogLine=(props)=>{
  return <span>{props.logline.points} points {props.logline.message} {document.configuration.hasChangePermission?<a href="#" onClick={()=>{if (window.confirm('Are you sure you want to remove the penalty?')){window.location.href=document.configuration.removePenaltyUrl(props.logline.id)}}}>Remove penalty</a>:null}<br/></span>
}

// Table Component
function App() {
  const [waypointData, setWaypointData] = React.useState([])
  const [contestant, setContestant] = React.useState()

  function processContestantData(data) {
    const freePoints = data.route.freewaypoint_set.map((waypoint) => { return waypoint.name })
    const regularPoints = data.route.waypoints.map((waypoint) => { return waypoint.name })
    const actualTimes = data.actualgatetime_set.reduce((previous, current) => ({ ...previous, [current.gate]: moment(current.time) }),{})
    const scoreLogs = groupByGate(data.scorelogentry_set)
    const regular = data.route.waypoints.map((waypoint) => {
      return {
        waypoint_name: waypoint.name,
        waypoint_time: waypoint.time_check ? moment.duration(data.relative_gate_times[waypoint.name] * 1000) : null,
        is_free: freePoints.includes(waypoint.name),
        absolute_expected_time: moment(data.absolute_gate_times[waypoint.name]),
        absolute_actual_time: actualTimes[waypoint.name] ?moment(actualTimes[waypoint.name]) : null,
        score_log: scoreLogs[waypoint.name] || null
      }
    })
    const free = data.route.freewaypoint_set.filter((waypoint) => { return !regularPoints.includes(waypoint.name) }).map((waypoint) => {
      return { waypoint_name: waypoint.name, waypoint_time: null, is_free: true }
    })
    setWaypointData(regular.concat(free))
    setContestant(data)
  }

  function fetchContestant() {
    fetch(document.configuration.thisContestantDataUrl, {
      method: "GET",
    }).then(response => {
      if (!response.ok) {
        throw new Error(response.statusText)
      }
      return response.json()
    })
      .then(data => {
        processContestantData(data)
      })
  }

  function putWaypointData() {
    fetch(document.configuration.thisContestantPutGateTimesUrl, {
      method: "POST",
      body: JSON.stringify(waypointData.map((w) => {
        let a = { waypoint_name: w.waypoint_name }
        if (w.waypoint_time) {
          a.waypoint_time = w.waypoint_time.asSeconds()
        }
        return a
      })),
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCookie(),
        "Content-Type": "application/json"
      }
    }).then(response => {
      if (!response.ok) {
        fetchContestant()
        response.text().then(text => {
          alert(text)
          throw new Error(text)
        })
      }
      return response.json()
    })
      .then(data => {
        processContestantData(data)
        window.location.href=document.configuration.thisNavigationTaskDetailsUrl
      })
  }

  useEffect(fetchContestant, [])
  const editableCell = ({ getValue, row: { index }, column: { id }, table }) => {
    const initialValue = getValue()
    // We need to keep and update the state of the cell normally
    const [value, setValue] = React.useState(initialValue)

    // When the input is blurred, we'll call our table meta's updateData function
    const onBlur = () => {
      table.options.meta?.updateData(index, id, value)
    }

    // If the initialValue is changed external, sync it up with our state
    React.useEffect(() => {
      setValue(initialValue)
    }, [initialValue])

    return (
      <input
        value={value}
        onChange={e => setValue(e.target.value)}
        onBlur={onBlur}
      />
    )
  }

  function isTimeInOrder(rowIndex) {
    const myTime = waypointData[rowIndex].waypoint_time
    if (!myTime) { return true }
    for (let i = 0; i < waypointData.length; i++) {
      if (i == rowIndex || !waypointData[i].waypoint_time) { continue }
      if (myTime.asMilliseconds() == waypointData[i].waypoint_time.asMilliseconds()) { return false }
      if ((i < rowIndex && myTime.asMilliseconds() < waypointData[i].waypoint_time.asMilliseconds()) || (i > rowIndex && myTime.asMilliseconds() > waypointData[i].waypoint_time.asMilliseconds())) { return false }
    }
    return true
  }
  const editable = !(contestant && (contestant.contestanttrack.calculator_started || contestant.contestanttrack.calculator_finished))
  const columns = React.useMemo(
    () => [
      // Create a dedicated drag handle column. Alternatively, you could just set up dnd events on the rows themselves.
      {
        id: 'drag-handle',
        header: 'Move',
        cell: ({ row }) => row.original.is_free && editable ? <RowDragHandleCell rowId={row.id} /> : null,
        size: 60,
      },
      {
        accessorKey: 'waypoint_name',
        cell: info => info.getValue(),
        header: 'Waypoint',
      },
      {
        accessorFn: row => row.waypoint_time ? row.waypoint_time.format("hh:mm:ss", { trim: 'large', stopTrim: "h" }) : '',
        id: 'waypoint_time',
        header: 'Relative time',
        cell: !editable ? info => info.getValue() : editableCell
      },
      {
        accessorKey: 'absolute_expected_time',
        header: 'Expected time',
        cell: info => info.getValue()?info.getValue().format('HH:mm:ss'):'--',
      },
      {
        accessorKey: 'absolute_actual_time',
        header: 'Actual time',
        cell: info => info.getValue()?info.getValue().format('HH:mm:ss'):'--',
      },
      {
        accessorFn: row => row.absolute_actual_time ? moment.duration(moment(row.absolute_actual_time).diff(moment(row.absolute_expected_time))).format("hh:mm:ss", { trim: 'large', stopTrim: "h" }) : '--',
        id: 'offset',
        header: 'Offset (s)'
      },
      {
        accessorKey: 'score_log',
        header: 'Log',
        cell: log => log.getValue() ? log.getValue().map((logline) => <LogLine logline={logline} />) : null
      }
    ],
    [editable]
  )

  const dataIds = React.useMemo(
    () => waypointData?.map(({ waypoint_name }) => waypoint_name),
    [waypointData]
  )


  const table = useReactTable({
    data: waypointData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: row => row.waypoint_name, //required because row indexes will change
    debugTable: true,
    debugHeaders: true,
    meta: {
      updateData: (rowIndex, columnId, value) => {
        setWaypointData(old =>
          old.map((row, index) => {
            if (index === rowIndex) {
              return {
                ...old[rowIndex],
                [columnId]: moment.duration(value),
              }
            }
            return row
          })
        )
      },
    },
    debugTable: true,
    debugColumns: true,
  })

  // reorder rows after drag & drop
  function handleDragEnd(event) {
    const { active, over } = event
    if (active && over && active.id !== over.id) {
      setWaypointData(data => {
        const oldIndex = dataIds.indexOf(active.id)
        const newIndex = dataIds.indexOf(over.id)
        return arrayMove(data, oldIndex, newIndex) //this is just a splice util
      })
    }
  }

  const sensors = useSensors(
    useSensor(MouseSensor, {}),
    useSensor(TouchSensor, {}),
    useSensor(KeyboardSensor, {})
  )

  const getRowProps = (context) => {
    console.log(context)
    if (!isTimeInOrder(context.index)) {
      return { className: 'highlightRow' }
    }
  }
  1
  return (
    // NOTE: This provider creates div elements, so don't nest inside of <table> elements
    <DndContext
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis]}
      onDragEnd={handleDragEnd}
      sensors={sensors}
    >
      <div className="p-2">
        <div className="h-4" />
        <table className='table striped bordered hover responsive'>
          <thead>
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th key={header.id} colSpan={header.colSpan}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            <SortableContext
              items={dataIds}
              strategy={verticalListSortingStrategy}
            >
              {table.getRowModel().rows.map(row => (
                <DraggableRow key={row.id} row={row} {...getRowProps(row)} />
              ))}
            </SortableContext>
          </tbody>
        </table>
        <div className="h-4">
          {editable ?
            <button onClick={() => putWaypointData()} className="btn btn-primary">
              Save
            </button> : null}
          <a href={document.configuration.thisNavigationTaskDetailsUrl} className='btn btn-secondary' role='button'>Back</a>
        </div>
        {/* <pre>{JSON.stringify(waypointData, null, 2)}</pre> */}
      </div>
    </DndContext>
  )
}

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Failed to find the root element')

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
