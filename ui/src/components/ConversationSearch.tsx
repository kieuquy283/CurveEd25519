/**
 * Search conversations component.
 */

"use client";

import React, { useState } from "react";
import { Search, X } from "lucide-react";
import { useContactStore } from "@/store/useContactStore";

interface ConversationSearchProps {
  onSearch: (query: string) => void;
}

export function ConversationSearch({ onSearch }: ConversationSearchProps) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const searchContacts = useContactStore((s) => s.searchContacts);

  const results = query.trim() ? searchContacts(query) : [];

  const handleChange = (value: string) => {
    setQuery(value);
    onSearch(value);
    setIsOpen(!!value.trim());
  };

  const handleClear = () => {
    setQuery("");
    onSearch("");
    setIsOpen(false);
  };

  return (
    <div className="px-3 pb-3 border-b border-zinc-800">
      <div className="relative">
        <Search
          size={16}
          className="absolute left-3 top-3 text-zinc-500"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Search conversations..."
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg pl-9 pr-9 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-3 text-zinc-500 hover:text-zinc-300"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Search results dropdown */}
      {isOpen && results.length > 0 && (
        <div className="mt-2 bg-zinc-800 border border-zinc-700 rounded-lg overflow-hidden">
          {results.slice(0, 5).map((contact) => (
            <div
              key={contact.id}
              className="px-3 py-2 hover:bg-zinc-700 cursor-pointer text-sm text-zinc-300 border-b border-zinc-700 last:border-b-0"
            >
              {contact.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
