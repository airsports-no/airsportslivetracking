import React, { CSSProperties, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import moment from 'moment';


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
  type DragEndEvent,
  type UniqueIdentifier,
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
const RowDragHandleCell = ({ rowId }: { rowId: string }) => {
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
const DraggableRow = ({ row }: { row: Row<Waypoint> }) => {
  const { transform, transition, setNodeRef, isDragging } = useSortable({
    id: row.original.waypoint_name,
  })

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform), //let dnd-kit do its thing
    transition: transition,
    opacity: isDragging ? 0.8 : 1,
    zIndex: isDragging ? 1 : 0,
    position: 'relative',
  }
  return (
    // connect row ref to dnd-kit, apply important styles
    <tr ref={setNodeRef} style={style}>
      {row.getVisibleCells().map(cell => (
        <td key={cell.id} style={{ width: cell.column.getSize() }}>
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </td>
      ))}
    </tr>
  )
}

type Waypoint = { waypoint_name: string, waypoint_time: string };
type Route = { waypoints: Array<any>, freewaypoint_set: Array<any> }
type Contestant = { route: Route, relative_gate_times: any }

// Table Component
function App() {
  const [waypointData, setWaypointData] = React.useState()

  function fetchContestant() {
    const contestant = fetch(document.configuration.thisContestantDataUrl, {
      method: "GET",
    })..then(response => {
      if (!response.ok) {
        throw new Error(response.statusText)
      }
      return response.json() as Promise<Contestant>
    })
      .then(data => {
        return data
      })
    const regular=contestant.route.waypoints.map((waypoint) => {
      return { waypoint_name: waypoint.name, waypoint_time: moment.duration(contestant.relative_gate_times[waypoint.name] )}
    })
    const free=contestant.freewaypoint_set.map((waypoint)=>{
      return {waypoint_name:waypoint.name,waypoint_time:null}
    })
    setWaypointData(regular.concat(free))
  }

  useEffect(fetchContestant)

  const columns = React.useMemo<ColumnDef<Waypoint>[]>(
    () => [
      // Create a dedicated drag handle column. Alternatively, you could just set up dnd events on the rows themselves.
      {
        id: 'drag-handle',
        header: 'Move',
        cell: ({ row }) => <RowDragHandleCell rowId={row.id} />,
        size: 60,
      },
      {
        accessorKey: 'waypoint_name',
        cell: info => info.getValue(),
      },
      {
        accessorKey: 'waypoint_time',
        cell: info => info.getValue(),
      },
    ],
    []
  )

  const dataIds = React.useMemo<UniqueIdentifier[]>(
    () => data?.map(({ waypoint_name }) => waypoint_name),
    [waypointData]
  )


  const table = useReactTable({
    contestantData: waypointData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: row => row.id, //required because row indexes will change
    debugTable: true,
    debugHeaders: true,
    debugColumns: true,
  })

  // reorder rows after drag & drop
  function handleDragEnd(event: DragEndEvent) {
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
        <div className="h-4" />
        <table>
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
                <DraggableRow key={row.id} row={row} />
              ))}
            </SortableContext>
          </tbody>
        </table>
        <pre>{JSON.stringify(waypointData, null, 2)}</pre>
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
