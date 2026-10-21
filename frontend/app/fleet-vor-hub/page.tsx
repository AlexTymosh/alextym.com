import type {Metadata} from "next";
import FleetApp from "./FleetApp";

export const metadata:Metadata={title:"Fleet VOR Hub · Demo",description:"Synthetic fleet operations workspace",robots:{index:false,follow:false}};
export default function FleetVorDemoPage(){return <FleetApp/>;}
