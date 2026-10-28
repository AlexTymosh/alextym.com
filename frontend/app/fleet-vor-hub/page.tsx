import type {Metadata} from "next";
import { FleetHubApp } from "@fleet-hub";

export const metadata:Metadata={title:"Fleet VOR Hub · Demo",description:"Synthetic fleet operations workspace",robots:{index:false,follow:false}};
export default function FleetVorDemoPage(){return <FleetHubApp/>;}
