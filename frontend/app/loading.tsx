import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[60vh] p-8">
      <div className="w-full max-w-xl space-y-6">
        <Skeleton className="h-8 w-48 mx-auto" />
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-12 w-40 mx-auto rounded-lg" />
      </div>
    </div>
  );
}
