"use client";
import { createContext, useContext } from "react";
import type { BackTheme } from "./table-interaction";
export const CardBackContext = createContext<BackTheme>("classic");
export const useCardBackTheme = () => useContext(CardBackContext);
