"use client";

import { useEffect, useState } from "react";

interface Note {
  id: number;
  content: string;
  category: string | null;
  is_task: number;
  file_path: string | null;
  code_snippet: string | null;
  web_context: string | null;
  created_at: string;
}

export default function Home() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedNote, setExpandedNote] = useState<number | null>(null);

  // Fake auth state
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [loginInput, setLoginInput] = useState("");

  useEffect(() => {
    if (currentUser) {
      fetchNotes(currentUser);
    }
  }, [currentUser]);

  const fetchNotes = async (user_id: string) => {
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8001/api/notes`, {
        headers: {
          "X-User-ID": user_id
        }
      });
      const data = await res.json();
      data.sort((a: Note, b: Note) => b.id - a.id);
      setNotes(data);
    } catch (error) {
      console.error("Failed to fetch notes:", error);
    } finally {
      setLoading(false);
    }
  };

  const categories = ["All", "Tasks", ...Array.from(new Set(notes.map(n => n.category).filter(Boolean)))];

  const filteredNotes = notes.filter(n => {
    // 1. Search Query Filter
    const matchesSearch = n.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (n.file_path || "").toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    // 2. Category Filter
    if (filter === "All") return true;
    if (filter === "Tasks") return n.is_task === 1;
    return n.category === filter;
  });

  if (!currentUser) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center font-sans">
        <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px]" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-fuchsia-600/20 blur-[120px]" />
        </div>
        <div className="w-full max-w-sm p-8 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-md shadow-2xl">
          <h2 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-fuchsia-400 bg-clip-text text-transparent mb-6 text-center">
            Login
          </h2>
          <form
            onSubmit={(e) => { e.preventDefault(); if (loginInput.trim()) setCurrentUser(loginInput.trim()); }}
            className="flex flex-col gap-4"
          >
            <input
              type="text"
              placeholder="Enter Workspace ID"
              value={loginInput}
              onChange={(e) => setLoginInput(e.target.value)}
              className="w-full bg-black/20 border border-white/10 rounded-xl py-3 px-4 text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-500"
              required
            />
            <button
              type="submit"
              className="w-full py-3 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white font-bold transition-all shadow-[0_0_15px_rgba(99,102,241,0.5)]"
            >
              Access Workspace
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 font-sans selection:bg-indigo-500/30">

      {/* Background Orbs */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-fuchsia-600/20 blur-[120px]" />
      </div>

      <main className="max-w-6xl mx-auto px-6 py-12">

        {/* Header */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <h1 className="text-5xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 to-fuchsia-400 bg-clip-text text-transparent mb-3">
              Second Brain
            </h1>
            <p className="text-slate-400 text-lg">Your AI-Powered Vector Workspace</p>
          </div>

          <div className="flex gap-4">
            <div className="px-5 py-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
              <span className="block text-sm text-slate-400 font-medium mb-1">Total Notes</span>
              <span className="text-2xl font-bold text-white">{notes.length}</span>
            </div>
            <div className="px-5 py-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
              <span className="block text-sm text-slate-400 font-medium mb-1">Open Tasks</span>
              <span className="text-2xl font-bold text-fuchsia-400">{notes.filter(n => n.is_task).length}</span>
            </div>
            <div className="px-5 py-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md flex flex-col items-end">
              <span className="block text-sm text-slate-400 font-medium mb-1">Authenticated As</span>
              <div className="flex items-center gap-3">
                <span className="text-fuchsia-400 font-bold">{currentUser}</span>
                <button
                  onClick={() => { setCurrentUser(null); setLoginInput(""); setNotes([]); }}
                  className="text-xs px-2 py-1 bg-white/10 hover:bg-red-500/80 rounded-md transition-colors"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Toolbar: Search and Filters */}
        <div className="flex flex-col md:flex-row gap-4 mb-10 items-center justify-between bg-white/5 p-4 rounded-2xl border border-white/10 backdrop-blur-sm">
          <div className="relative w-full md:max-w-md">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              placeholder="Search through notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-black/20 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-500 transition-all"
            />
          </div>

          <div className="flex flex-wrap gap-2 justify-end w-full">
            {categories.map((cat) => (
              <button
                key={cat as string}
                onClick={() => setFilter(cat as string)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${filter === cat
                  ? "bg-indigo-500 text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]"
                  : "bg-white/5 text-slate-300 hover:bg-white/10 border border-white/5"
                  }`}
              >
                {cat?.toString().replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Notes Masonry layout imitation (Grid with dense packing) */}
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 items-start">
            {filteredNotes.map((note) => {
              const isExpanded = expandedNote === note.id;
              const hasExtraContent = !!note.code_snippet || !!note.web_context;

              return (
                <div
                  key={note.id}
                  onClick={() => hasExtraContent && setExpandedNote(isExpanded ? null : note.id)}
                  className={`group relative flex flex-col p-6 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-md transition-all duration-300 ${hasExtraContent ? 'cursor-pointer hover:bg-white/10 hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10' : ''}`}
                >
                  <div className="flex justify-between items-start mb-4">
                    <span className="text-xs font-mono text-slate-500">#{note.id}</span>
                    <div className="flex gap-2">
                      {note.is_task === 1 && (
                        <span className="px-2.5 py-1 rounded-full bg-fuchsia-500/20 text-fuchsia-300 text-[10px] font-bold tracking-wider uppercase border border-fuchsia-500/30">
                          Task
                        </span>
                      )}
                      {note.category && (
                        <span className="px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-[10px] font-bold tracking-wider uppercase border border-indigo-500/30">
                          {note.category.replace("_", " ")}
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-slate-200 leading-relaxed font-medium mb-6 break-words whitespace-pre-wrap">
                    {note.content}
                  </p>

                  {/* Expandable Rich Data */}
                  {hasExtraContent && (
                    <div className={`overflow-hidden transition-all duration-500 ease-in-out ${isExpanded ? 'max-h-96 opacity-100 mb-6' : 'max-h-0 opacity-0'}`}>
                      {note.code_snippet && (
                        <div className="mb-4">
                          <p className="text-xs text-indigo-400 font-bold uppercase tracking-wider mb-2">Code Snippet</p>
                          <pre className="bg-black/40 p-3 rounded-xl border border-white/5 text-xs text-slate-300 font-mono overflow-auto max-h-40">
                            {note.code_snippet}
                          </pre>
                        </div>
                      )}
                      {note.web_context && (
                        <div>
                          <p className="text-xs text-fuchsia-400 font-bold uppercase tracking-wider mb-2">Scraped Context</p>
                          <div className="bg-fuchsia-950/20 p-3 rounded-xl border border-fuchsia-500/10 text-xs text-slate-300 overflow-auto max-h-40 italic">
                            {note.web_context.length > 200 ? note.web_context.substring(0, 200) + "..." : note.web_context}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {hasExtraContent && !isExpanded && (
                    <div className="mt-[-10px] mb-4 flex justify-center">
                      <span className="text-xs text-indigo-400/50 group-hover:text-indigo-400 transition-colors">Click to view context</span>
                    </div>
                  )}

                  <div className="mt-auto pt-4 border-t border-white/5 flex flex-col gap-2">
                    {note.file_path && (
                      <div className="flex items-center gap-2 text-xs text-indigo-400 font-mono">
                        <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <span className="truncate" title={note.file_path}>{note.file_path.split("/").pop()}</span>
                      </div>
                    )}
                    {note.created_at && (
                      <span className="text-xs text-slate-500">
                        {new Date(note.created_at).toLocaleDateString(undefined, {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        })}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
