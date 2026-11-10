// Vite resolves `?url` imports to the address of the emitted asset.
declare module '*.wasm?url' {
    const url: string;
    export default url;
}
