import { useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

const subscribe = () => () => {};
const slotSnapshot = () => document.getElementById("preferans-room-return-slot");
const serverSnapshot = () => null;

/** Host header is optional; embedded previews retain an accessible local return action. */
export function RoomReturn({onReturn}: {onReturn:()=>void}) {
  const slot=useSyncExternalStore(subscribe,slotSnapshot,serverSnapshot);
  const action=<div className="preferans-site-room-return">
    {slot&&<span className="preferans-site-divider" aria-hidden="true">|</span>}
    <button type="button" onClick={onReturn} title="К выбору комнаты" aria-label="К выбору комнаты">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 12H5m7-7-7 7 7 7"/></svg>
      <span>К выбору комнаты</span>
    </button>
  </div>;
  return slot?createPortal(action,slot):action;
}
