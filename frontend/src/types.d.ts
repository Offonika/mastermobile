declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}

declare module '*.css';

declare global {
  interface Window {
    __ASSISTANT_DEBUG__?: string | number | boolean | null;
  }

  interface ImportMetaEnv {
    readonly VITE_ASSISTANT_DEBUG?: string;
    readonly ASSISTANT_DEBUG?: string;
  }
}

export {};
