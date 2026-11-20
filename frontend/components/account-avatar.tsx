import Image from "next/image";

export function AccountAvatar({ name, url, size = 40 }: { name: string; url: string | null; size?: number }) {
  const initials = name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return url ? <Image src={url} alt="" width={size} height={size} unoptimized
    style={{ borderRadius: "50%", objectFit: "cover", flexShrink: 0 }} referrerPolicy="no-referrer" />
    : <span aria-hidden="true" style={{ width: size, height: size, display: "grid", placeItems: "center",
      borderRadius: "50%", background: "var(--accent-soft)", color: "var(--text)", flexShrink: 0, fontWeight: 650 }}>
      {initials}
    </span>;
}
