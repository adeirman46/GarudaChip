import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// NOTE: StrictMode intentionally omitted — it double-invokes state updaters in dev,
// which duplicates streamed transcript blocks. The updaters are now pure regardless.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
