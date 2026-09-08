import React, { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { MessageCircle, Trash2 } from "lucide-react";

/**
 * Comment + Delete buttons for a Visi row. Handles its own dialog/confirm,
 * undo toast for the delete, and calls onChanged so the parent list reloads.
 */
export function VisiQuickActions({ visi, onChanged }) {
  const [showComment, setShowComment] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  const send = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      await api.post(`/visis/${visi.id}/comment`, { text: text.trim() });
      toast.success("Comment added");
      setText("");
      setShowComment(false);
      onChanged?.();
    } catch (e) {
      toast.error("Could not add comment");
    } finally {
      setSending(false);
    }
  };

  const del = async () => {
    if (!window.confirm(`Delete Visi ${visi.code}? You can undo this right after.`)) return;
    try {
      await api.delete(`/visis/${visi.id}`);
      onChanged?.();
      toast("Visi deleted", {
        action: {
          label: "Undo",
          onClick: async () => {
            try {
              await api.post(`/visis/${visi.id}/restore`);
              toast.success("Visi restored");
              onChanged?.();
            } catch { toast.error("Could not restore"); }
          },
        },
      });
    } catch {
      toast.error("Could not delete Visi");
    }
  };

  return (
    <>
      <Button size="icon" variant="ghost" className="h-9 w-9" title="Comment" onClick={(e) => { e.stopPropagation(); setShowComment(true); }} data-testid={`visi-comment-btn-${visi.id}`}>
        <MessageCircle size={16} className="text-slate-500" />
      </Button>
      <Button size="icon" variant="ghost" className="h-9 w-9" title="Delete" onClick={(e) => { e.stopPropagation(); del(); }} data-testid={`visi-delete-btn-${visi.id}`}>
        <Trash2 size={16} className="text-slate-400 hover:text-red-500" />
      </Button>

      <Dialog open={showComment} onOpenChange={setShowComment}>
        <DialogContent className="max-w-md" data-testid="quick-comment-dialog">
          <DialogHeader>
            <DialogTitle className="text-base">Comment on {visi.code}</DialogTitle>
          </DialogHeader>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your comment…" rows={3} autoFocus data-testid="quick-comment-input" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowComment(false)}>Cancel</Button>
            <Button onClick={send} disabled={!text.trim() || sending} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="quick-comment-send">Post comment</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
