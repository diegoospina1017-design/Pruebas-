declare module "*.module.css" {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module "plotly.js-dist-min" {
  const plotly: any;
  export default plotly;
}
