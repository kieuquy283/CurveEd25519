/**
 * Skeleton loader component for better UX during loading.
 */

"use client";

import React from "react";

export function SkeletonAvatar() {
  return (
    <div className="w-10 h-10 rounded-full bg-zinc-800 animate-pulse" />
  );
}

export function SkeletonText() {
  return (
    <div className="h-4 bg-zinc-800 rounded animate-pulse" />
  );
}

export function SkeletonMessageBubble() {
  return (
    <div className="flex gap-3">
      <SkeletonAvatar />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-32 bg-zinc-800 rounded animate-pulse" />
        <div className="h-8 w-48 bg-zinc-800 rounded-lg animate-pulse" />
      </div>
    </div>
  );
}

export function SkeletonConversationItem() {
  return (
    <div className="flex items-start gap-3 px-3 py-3">
      <SkeletonAvatar />
      <div className="flex-1 min-w-0">
        <div className="h-4 w-32 bg-zinc-800 rounded animate-pulse mb-2" />
        <div className="h-3 w-full bg-zinc-800 rounded animate-pulse" />
      </div>
    </div>
  );
}

export function MessageListSkeleton() {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <SkeletonMessageBubble key={i} />
      ))}
    </div>
  );
}

export function ConversationListSkeleton() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="flex flex-col gap-1 p-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonConversationItem key={i} />
        ))}
      </div>
    </div>
  );
}
