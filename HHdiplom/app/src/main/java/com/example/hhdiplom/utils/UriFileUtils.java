package com.example.hhdiplom.utils;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

public class UriFileUtils {

    private UriFileUtils() {}

    public static File copyUriToCache(Context context, Uri uri) throws Exception {
        ContentResolver resolver = context.getContentResolver();
        String name = queryName(resolver, uri);
        if (name == null || name.trim().isEmpty()) {
            name = "video_" + System.currentTimeMillis() + ".mp4";
        }
        File outFile = new File(context.getCacheDir(), name);

        try (InputStream in = resolver.openInputStream(uri); FileOutputStream out = new FileOutputStream(outFile)) {
            if (in == null) throw new IllegalStateException("Не удалось открыть файл");
            byte[] buf = new byte[8192];
            int len;
            while ((len = in.read(buf)) > 0) {
                out.write(buf, 0, len);
            }
            out.flush();
        }
        return outFile;
    }

    private static String queryName(ContentResolver resolver, Uri uri) {
        Cursor cursor = null;
        try {
            cursor = resolver.query(uri, null, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0) return cursor.getString(idx);
            }
        } catch (Exception ignored) {
        } finally {
            if (cursor != null) cursor.close();
        }
        return null;
    }
}
