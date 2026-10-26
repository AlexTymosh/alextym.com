"use client";

import Image from "next/image";
import demoVan from "./assets/fleet-van-demo.webp";
import styles from "./vehicle-photo.module.css";

/** Synthetic demonstration photograph; not evidence of this registered vehicle. */
export default function VehiclePhoto({ model, registration }: { model: string; registration: string }) {
  const van = /transit|sprinter|crafter|trafic|vito|master|daily|boxer|ducato|relay|vivaro/i.test(model);
  return (
    <figure className={styles.figure} title={`Illustrative model photograph only · ${registration}`}>
      {van ? <Image className={styles.image} src={demoVan} alt={`Illustrative panel van photograph for ${model}; not the actual vehicle ${registration}`} width={160} height={116} priority />
           : <div className={styles.placeholder} role="img" aria-label={`No demonstration photograph for ${model}`}><span aria-hidden="true">▱</span><small>Image unavailable</small></div>}
      
    </figure>
  );
}
