"use client";

import { useEffect, useState } from "react";
import { Copy, ExternalLink, Linkedin, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";
import { apiUrl } from "@/lib/apiBase";
import { BrandLead, LinkedInContact } from "@/lib/types";
import { Button } from "./ui/button";

const CONNECTION_NOTE_MAX_CHARS = 200;

interface LinkedInMessageModalProps {
  brand: BrandLead;
  contacts: LinkedInContact[];
  onClose: () => void;
  /** The profile was opened. This doesn't confirm the message was sent. */
  onProfileOpened: () => void;
}

async function copyText(text: string, success: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(success);
  } catch {
    toast.error("Não foi possível copiar. Seleciona o texto e copia manualmente.");
  }
}

export function LinkedInMessageModal({ brand, contacts, onClose, onProfileOpened }: LinkedInMessageModalProps) {
  const [selected, setSelected] = useState(0);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [profileUrl, setProfileUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const contact = contacts[selected];

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    (async () => {
      try {
        const response = await fetch(apiUrl("/api/linkedin/draft"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ brandData: brand, contact }),
        });
        if (!response.ok) throw new Error("draft failed");
        const data = await response.json();
        if (cancelled) return;
        setNote(data.connection_note);
        setMessage(data.message);
        setProfileUrl(data.profile_url);
        setIsLoading(false);
      } catch {
        if (cancelled) return;
        toast.error("Não foi possível gerar a mensagem.");
        onClose();
      }
    })();
    return () => {
      cancelled = true;
    };
    // Only a different contact needs a new draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  // Everything runs directly in the click: browsers block clipboard writes and
  // pop-ups that happen after a network wait, which is why this modal exists.
  const handleCopyAndOpen = () => {
    if (!profileUrl) return;
    window.open(profileUrl, "_blank", "noopener,noreferrer");
    void copyText(note, "Nota copiada. Cola-a no pedido de ligação.");
    onProfileOpened();
  };

  const noteTooLong = note.length > CONNECTION_NOTE_MAX_CHARS;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Mensagem LinkedIn para ${brand.name}`}
        className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl border border-border animate-in zoom-in-95 duration-200"
      >
        <div className="flex items-center justify-between p-5 border-b border-border bg-muted/30">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-[#0A66C2]/10 text-[#0A66C2]">
              <Linkedin className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-foreground truncate">Mensagem LinkedIn: {brand.name}</h3>
              <p className="text-xs text-muted-foreground">Revê o texto antes de enviar</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Fechar" className="p-2 hover:bg-muted rounded-full transition-colors">
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {contacts.length > 1 && (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-foreground mb-2">Para quem</legend>
              {contacts.map((c, i) => (
                <label
                  key={c.linkedin_url}
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                    i === selected ? "border-[#0A66C2] bg-[#0A66C2]/5" : "border-border hover:bg-muted/50"
                  }`}
                >
                  <input
                    type="radio"
                    name="linkedin-contact"
                    checked={i === selected}
                    onChange={() => setSelected(i)}
                    className="accent-[#0A66C2]"
                  />
                  <span className="text-sm min-w-0">
                    <span className="font-medium text-foreground">{c.name}</span>
                    {c.role && <span className="text-muted-foreground"> · {c.role}</span>}
                  </span>
                </label>
              ))}
            </fieldset>
          )}

          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" />
              A escrever a mensagem para {contact?.name}...
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <label htmlFor="linkedin-note" className="text-sm font-medium text-foreground">
                  1. Nota do pedido de ligação
                </label>
                <textarea
                  id="linkedin-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="w-full h-24 p-3 rounded-xl border border-border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-lanca-yellow/50 focus:border-lanca-yellow transition-all"
                />
                <p className={`text-[11px] text-right ${noteTooLong ? "text-rose-600 font-medium" : "text-muted-foreground"}`}>
                  {note.length}/{CONNECTION_NOTE_MAX_CHARS}
                  {noteTooLong && " · demasiado longa para contas LinkedIn gratuitas"}
                </p>
                <Button
                  onClick={handleCopyAndOpen}
                  disabled={!profileUrl || !note.trim()}
                  className="w-full h-11 rounded-xl gap-2 font-semibold bg-[#0A66C2] hover:bg-[#004182] text-white"
                >
                  <ExternalLink className="h-4 w-4" />
                  Copiar e abrir LinkedIn
                </Button>
              </div>

              <div className="space-y-2 pt-4 border-t border-border">
                <label htmlFor="linkedin-message" className="text-sm font-medium text-foreground">
                  2. Mensagem depois de aceitar
                </label>
                <textarea
                  id="linkedin-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="w-full h-44 p-3 rounded-xl border border-border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-lanca-yellow/50 focus:border-lanca-yellow transition-all"
                />
                <Button
                  variant="outline"
                  onClick={() => void copyText(message, "Mensagem copiada.")}
                  disabled={!message.trim()}
                  className="w-full h-10 rounded-xl gap-2"
                >
                  <Copy className="h-4 w-4" />
                  Copiar mensagem
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
