"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, X, Send, MessageSquare } from "lucide-react";
import { Button } from "./ui/button";

interface FeedbackModalProps {
  brandName: string;
  feedbackType: "up" | "down";
  onClose: () => void;
  onSubmit: (comment: string) => Promise<void>;
}

export function FeedbackModal({ brandName, feedbackType, onClose, onSubmit }: FeedbackModalProps) {
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comment || comment.length < 3) return;
    
    setIsSubmitting(true);
    try {
      await onSubmit(comment);
      onClose();
    } catch (error) {
      console.error("Error submitting feedback:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="bg-white rounded-2xl w-full max-w-md shadow-2xl border border-border overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-border bg-muted/30">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              feedbackType === "up" ? "bg-emerald-100 text-emerald-600" : "bg-rose-100 text-rose-600"
            }`}>
              {feedbackType === "up" ? <ThumbsUp className="h-5 w-5" /> : <ThumbsDown className="h-5 w-5" />}
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Feedback: {brandName}</h3>
              <p className="text-xs text-muted-foreground">
                {feedbackType === "up" ? "Diga-nos porque gostou desta marca" : "Porque é que esta marca não serve?"}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-muted rounded-full transition-colors">
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-2">
            <label htmlFor="comment" className="text-sm font-medium text-foreground flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
              Sua Mensagem
            </label>
            <textarea
              id="comment"
              autoFocus
              required
              placeholder={feedbackType === "up" ? "E.g. Estilo clássico perfeito, boa gama de preços..." : "E.g. Demasiado moderna para nós, ou preços inacessíveis..."}
              className="w-full h-32 p-4 rounded-xl border border-border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-lanca-yellow/50 focus:border-lanca-yellow transition-all scrollbar-thin"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <p className="text-[10px] text-muted-foreground flex justify-between">
              <span>Pelo menos 3 caracteres</span>
              <span>{comment.length} caracteres</span>
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="flex-1 h-11 rounded-xl"
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || comment.length < 3}
              className={`flex-[2] h-11 rounded-xl gap-2 font-semibold ${
                feedbackType === "up" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-rose-600 hover:bg-rose-700"
              } text-white shadow-lg`}
            >
              {isSubmitting ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              {isSubmitting ? "A Guardar..." : "Guardar Feedback"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Simple CSS for RefreshCw animation if not global
const RefreshCw = ({ className }: { className?: string }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    width="24" height="24" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className={className}
  >
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
    <path d="M16 16h5v5" />
  </svg>
);
