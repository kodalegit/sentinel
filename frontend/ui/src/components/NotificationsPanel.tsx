"use client";

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Bell, CheckCircle2, ChevronRight, Loader2 } from "lucide-react";
import { getNotifications, markNotificationRead } from "@/lib/api";
import type { CaseNotification } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

function formatNotificationTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function NotificationSection({
  title,
  description,
  notifications,
  onOpenCase,
  onMarkRead,
  markReadPendingId,
}: {
  title: string;
  description: string;
  notifications: CaseNotification[];
  onOpenCase: (notification: CaseNotification) => Promise<void>;
  onMarkRead: (notificationId: string) => void;
  markReadPendingId: string | null;
}) {
  if (notifications.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1 px-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="space-y-3">
        {notifications.map((notification) => {
          const isPending = markReadPendingId === notification.id;

          return (
            <div
              key={notification.id}
              className="rounded-2xl border border-border/70 bg-card/80 p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    {!notification.is_read && (
                      <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#c4412f]" />
                    )}
                    <p className="text-sm font-medium text-foreground">
                      {notification.case_title ?? "Case update"}
                    </p>
                  </div>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {notification.message}
                  </p>
                </div>
                {!notification.is_read && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="shrink-0 rounded-full"
                    onClick={() => onMarkRead(notification.id)}
                    disabled={isPending}
                    aria-label="Mark as read"
                  >
                    {isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
              <div className="mt-4 flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  {formatNotificationTime(notification.created_at)}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void onOpenCase(notification)}
                >
                  Open case
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function NotificationsPanel({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: notifications = [], isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(false),
    enabled: open,
  });

  const markReadMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["notification-count"] }),
      ]);
    },
  });

  const unreadNotifications = useMemo(
    () => notifications.filter((notification) => !notification.is_read),
    [notifications],
  );
  const readNotifications = useMemo(
    () => notifications.filter((notification) => notification.is_read),
    [notifications],
  );

  const handleMarkRead = (notificationId: string) => {
    markReadMutation.mutate(notificationId);
  };

  const handleOpenCase = async (notification: CaseNotification) => {
    if (!notification.is_read) {
      await markReadMutation.mutateAsync(notification.id);
    }
    onOpenChange(false);
    router.push(`/cases/${notification.case_id}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="left-auto right-0 top-0 h-screen w-full max-w-[420px] translate-x-0 translate-y-0 gap-0 rounded-none border-l border-border/80 p-0 sm:max-w-[420px]"
      >
        <DialogHeader className="border-b border-border/70 px-6 py-5 text-left">
          <DialogTitle className="flex items-center gap-3 text-xl">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
              <Bell className="h-5 w-5" />
            </span>
            Notifications
          </DialogTitle>
          <DialogDescription>
            Review case activity, mark items as read, and jump straight into the relevant investigation.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="h-[calc(100vh-105px)] px-6 py-5">
          {isLoading ? (
            <div className="flex h-48 items-center justify-center">
              <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex h-[50vh] flex-col items-center justify-center gap-3 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-full border border-border/70 bg-muted/40 text-muted-foreground">
                <Bell className="h-6 w-6" />
              </span>
              <div className="space-y-1">
                <p className="font-medium text-foreground">No notifications yet</p>
                <p className="text-sm text-muted-foreground">
                  New assignments and case updates will appear here.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-6 pb-6">
              <NotificationSection
                title="Unread"
                description="Recent updates that still need attention."
                notifications={unreadNotifications}
                onOpenCase={handleOpenCase}
                onMarkRead={handleMarkRead}
                markReadPendingId={markReadMutation.isPending ? markReadMutation.variables ?? null : null}
              />
              <NotificationSection
                title="Read"
                description="Previously reviewed notifications for reference."
                notifications={readNotifications}
                onOpenCase={handleOpenCase}
                onMarkRead={handleMarkRead}
                markReadPendingId={markReadMutation.isPending ? markReadMutation.variables ?? null : null}
              />
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
