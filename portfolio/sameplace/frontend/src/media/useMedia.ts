"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {MeshProvider} from "./mesh";
import {emptyView,type MediaView,type MediaFrame,type Send} from "./types";
import {DEFAULT_AUDIO,loadAudio,saveAudio,type AudioPreferences} from "./preferences";

export function useMedia(){
  const provider=useRef<MeshProvider|null>(null);
  const [view,setView]=useState<MediaView>(emptyView);
  const [audio,setAudio]=useState<AudioPreferences>(DEFAULT_AUDIO);
  const preferences=useRef<AudioPreferences>(DEFAULT_AUDIO);
  // Mount the controller above the scene, layout and future activity UI.
  useEffect(()=>{const instance=new MeshProvider(setView);provider.current=instance;return()=>{instance.dispose();provider.current=null;};},[]);
  useEffect(()=>{let active=true;const value=loadAudio();preferences.current=value;queueMicrotask(()=>{if(active)setAudio(value);});return()=>{active=false;};},[]);
  const updateAudio=useCallback((change:Partial<AudioPreferences>)=>{const next={...preferences.current,...change};preferences.current=next;saveAudio(next);setAudio(next);},[]);
  return {provider,view,audio,updateAudio,transport:(send:Send|null)=>provider.current?.transport(send),receive:(frame:MediaFrame)=>provider.current?.receive(frame)};
}
