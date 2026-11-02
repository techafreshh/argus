import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./index.css";
import App from "./App";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ChatDrawerProvider } from "@/chat/chat-drawer";

const el = document.getElementById("root");
if (el) {
  createRoot(el).render(
    <React.StrictMode>
      <BrowserRouter>
        <TooltipProvider delayDuration={200}>
          <ChatDrawerProvider>
            <App />
          </ChatDrawerProvider>
        </TooltipProvider>
      </BrowserRouter>
    </React.StrictMode>,
  );
}
