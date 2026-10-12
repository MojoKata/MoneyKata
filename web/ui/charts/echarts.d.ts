// The vendored ECharts build is used through charts/ only; its types are kept to what the
// wrapper calls rather than vendoring ECharts' 1 MB of declarations.
export interface EChart {
  setOption(option: object, notMerge?: boolean): void;
  resize(): void;
  dispose(): void;
  on(event: string, handler: (params: unknown) => void): void;
}
export function init(el: HTMLElement, theme?: string | object | null, opts?: object): EChart;
export function registerTheme(name: string, theme: object): void;
