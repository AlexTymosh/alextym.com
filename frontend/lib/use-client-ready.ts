"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => undefined;
const clientValue = () => true;
const serverValue = () => false;

export function useClientReady() {
  return useSyncExternalStore(subscribe, clientValue, serverValue);
}
