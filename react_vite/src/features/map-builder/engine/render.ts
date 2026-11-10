import type { LayerDefinition, SymbolName } from './layers';
import type { Frame, TileGrid } from './tiles';
import { TILE_SIZE } from './tiles';
import type { Feature, FeaturesByLayer } from './types';

/** Maps frame pixels (detail zoom) to the pixels of one zoom level's grid: `grid = frame * scale + offset`. */
export interface LevelTransform {
    scale: number;
    offsetX: number;
    offsetY: number;
}

export function levelTransform(frame: Frame, grid: TileGrid): LevelTransform {
    const scale = 2 ** (grid.zoom - frame.zoom);
    return {
        scale,
        offsetX: frame.originX * scale - grid.tileX0 * TILE_SIZE,
        offsetY: frame.originY * scale - grid.tileY0 * TILE_SIZE,
    };
}

export function drawSymbol(
    context: CanvasRenderingContext2D,
    x: number,
    y: number,
    symbol: SymbolName,
    size: number,
    color: string,
): void {
    const s = size;
    context.save();
    context.fillStyle = color;
    context.strokeStyle = color;
    context.setLineDash([]);
    context.beginPath();
    switch (symbol) {
        case 'triangle':
            context.moveTo(x, y - s);
            context.lineTo(x - s, y + s * 0.8);
            context.lineTo(x + s, y + s * 0.8);
            context.closePath();
            context.fill();
            break;
        case 'castle':
            context.fillRect(x - s, y - s * 0.6, 2 * s, 1.6 * s);
            for (const dx of [-s, -s / 3 + 0.5, s / 3 + 0.5]) context.fillRect(x + dx, y - s, s * 0.5, s * 0.5);
            break;
        case 'antenna':
            context.lineWidth = Math.max(1, s / 3);
            context.moveTo(x, y - s * 1.4);
            context.lineTo(x, y + s);
            context.moveTo(x - s * 0.8, y + s);
            context.lineTo(x, y - s * 0.2);
            context.lineTo(x + s * 0.8, y + s);
            context.stroke();
            break;
        case 'aerodrome':
            context.lineWidth = Math.max(1.2, s / 3.5);
            context.arc(x, y, s, 0, 2 * Math.PI);
            context.moveTo(x - s * 1.5, y);
            context.lineTo(x + s * 1.5, y);
            context.stroke();
            break;
        case 'wind':
            context.lineWidth = Math.max(1, s / 4);
            context.moveTo(x, y);
            context.lineTo(x, y + s * 1.4);
            for (const degrees of [-90, 30, 150]) {
                const angle = (degrees * Math.PI) / 180;
                context.moveTo(x, y);
                context.lineTo(x + Math.cos(angle) * s, y + Math.sin(angle) * s);
            }
            context.stroke();
            break;
        case 'mill':
            context.lineWidth = Math.max(1, s / 3);
            context.moveTo(x - s, y - s);
            context.lineTo(x + s, y + s);
            context.moveTo(x + s, y - s);
            context.lineTo(x - s, y + s);
            context.stroke();
            context.fillRect(x - s * 0.35, y - s * 0.35, s * 0.7, s * 0.7);
            break;
        case 'church':
            context.lineWidth = Math.max(1, s / 2.5);
            context.moveTo(x, y - s * 1.2);
            context.lineTo(x, y + s);
            context.moveTo(x - s * 0.7, y - s * 0.4);
            context.lineTo(x + s * 0.7, y - s * 0.4);
            context.stroke();
            break;
    }
    context.restore();
}

/** A small sample of how a layer is drawn, for the layer list. */
export function drawSwatch(canvas: HTMLCanvasElement, layer: LayerDefinition): void {
    const context = canvas.getContext('2d');
    if (!context) return;
    const { width, height } = canvas;
    context.clearRect(0, 0, width, height);
    // Map colours are designed for the light map background, whatever the page theme.
    context.fillStyle = '#f4f4f0';
    context.fillRect(0, 0, width, height);
    if (layer.kind === 'fill') {
        context.globalAlpha = layer.alpha;
        context.fillStyle = layer.color;
        context.fillRect(0, 0, width, height);
        context.globalAlpha = 1;
    } else if (layer.kind === 'line') {
        context.strokeStyle = layer.color;
        context.lineWidth = Math.max(1, layer.width);
        context.setLineDash(layer.dash ? layer.dash.map(length => length * 0.8) : []);
        context.beginPath();
        context.moveTo(3, height / 2);
        context.lineTo(width - 3, height / 2);
        context.stroke();
        context.setLineDash([]);
    } else {
        drawSymbol(context, width / 2, height / 2, layer.symbol, Math.min(layer.size * 1.2, height / 2 - 2.5), layer.color);
    }
}

/**
 * Draws the features of the given layers into a block of one zoom level's grid. The block's
 * top-left corner is (x0, y0) in grid pixels and maps to the canvas origin.
 *
 * Line widths and symbol sizes are multiplied by `styleScale`. With 1, every zoom level uses the
 * same weights in output pixels, so a lower level shows them over a larger area and looks busier,
 * like any tiled map. With the level's own scale factor (0.5 one level below the detail zoom), a
 * lower level looks like the detail level shrunk: finer, less crowded, more detail per pixel.
 */
export function drawFeatures(
    context: CanvasRenderingContext2D,
    x0: number,
    y0: number,
    width: number,
    height: number,
    layers: LayerDefinition[],
    features: FeaturesByLayer,
    transform: LevelTransform,
    styleScale = 1,
): void {
    const { scale } = transform;
    const dx = transform.offsetX - x0;
    const dy = transform.offsetY - y0;
    const margin = 16;
    const visible = (feature: Feature): boolean =>
        !(
            feature.box[2] * scale + dx < -margin ||
            feature.box[0] * scale + dx > width + margin ||
            feature.box[3] * scale + dy < -margin ||
            feature.box[1] * scale + dy > height + margin
        );
    const trace = (coordinates: Float32Array, close: boolean) => {
        context.moveTo(coordinates[0] * scale + dx, coordinates[1] * scale + dy);
        for (let i = 2; i < coordinates.length; i += 2) {
            context.lineTo(coordinates[i] * scale + dx, coordinates[i + 1] * scale + dy);
        }
        if (close) context.closePath();
    };

    context.save();
    context.lineJoin = 'round';
    context.lineCap = 'round';
    for (const layer of layers) {
        if (layer.kind === 'point') continue;
        const inBlock = (features[layer.id] ?? []).filter(visible);
        if (!inBlock.length) continue;
        if (layer.kind === 'fill') {
            // Multiply keeps the terrain shading visible through the colour.
            context.globalCompositeOperation = layer.opaque ? 'source-over' : 'multiply';
            context.globalAlpha = layer.alpha;
            context.fillStyle = layer.color;
            for (const feature of inBlock) {
                if (feature.kind !== 'polygon') continue;
                context.beginPath();
                for (const ring of feature.rings) trace(ring, true);
                context.fill('evenodd');
            }
            context.globalAlpha = 1;
            context.globalCompositeOperation = 'source-over';
        } else {
            context.fillStyle = layer.color;
            for (const feature of inBlock) {
                if (feature.kind !== 'polygon') continue;
                context.beginPath();
                for (const ring of feature.rings) trace(ring, true);
                context.fill('evenodd');
            }
            context.strokeStyle = layer.color;
            context.lineWidth = layer.width * styleScale;
            context.setLineDash((layer.dash ?? []).map(length => length * styleScale));
            context.beginPath();
            for (const feature of inBlock) if (feature.kind === 'line') trace(feature.line, false);
            context.stroke();
            context.setLineDash([]);
        }
    }
    // Symbols go on top of all lines and areas.
    for (const layer of layers) {
        if (layer.kind !== 'point') continue;
        for (const feature of features[layer.id] ?? []) {
            if (feature.kind !== 'point' || !visible(feature)) continue;
            drawSymbol(context, feature.point[0] * scale + dx, feature.point[1] * scale + dy, layer.symbol, layer.size * styleScale, layer.color);
        }
    }
    context.restore();
}
