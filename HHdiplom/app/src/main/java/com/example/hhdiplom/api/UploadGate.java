package com.example.hhdiplom.api;

import java.util.concurrent.atomic.AtomicInteger;

public final class UploadGate {
    private static final AtomicInteger active = new AtomicInteger(0);

    private UploadGate() {}

    public static void begin() { active.incrementAndGet(); }

    public static void end() {
        int v = active.decrementAndGet();
        if (v < 0) active.set(0);
    }

    public static boolean isUploading() { return active.get() > 0; }
}
