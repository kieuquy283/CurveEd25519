"use client";
import React from "react";
import Image from "next/image";

export default function ContactAvatar({
  src,
  alt,
  size = 40,
}: {
  src?: string;
  alt?: string;
  size?: number;
}) {
  const fallback = (
    <div
      style={{ width: size, height: size }}
      className="rounded-full bg-slate-700 flex items-center justify-center text-slate-300"
    >
      {alt?.charAt(0)?.toUpperCase() ?? "?"}
    </div>
  );

  if (!src) return fallback;

  return (
    <div style={{ width: size, height: size }} className="rounded-full overflow-hidden">
      <Image src={src} alt={alt ?? "avatar"} width={size} height={size} />
    </div>
  );
}
