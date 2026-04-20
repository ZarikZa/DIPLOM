package com.example.hhdiplom.api;

import java.io.IOException;
import okhttp3.Interceptor;
import okhttp3.MediaType;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

public class ForceUtf8JsonInterceptor implements Interceptor {
    @Override
    public Response intercept(Chain chain) throws IOException {
        Response response = chain.proceed(chain.request());

        ResponseBody body = response.body();
        if (body == null) return response;

        MediaType ct = body.contentType();
        String subtype = (ct != null && ct.subtype() != null) ? ct.subtype().toLowerCase() : "";

        if (subtype.contains("json")) {
            byte[] bytes = body.bytes(); // читаем 1 раз
            MediaType utf8 = MediaType.get("application/json; charset=utf-8");
            ResponseBody newBody = ResponseBody.create(bytes, utf8);
            return response.newBuilder().body(newBody).build();
        }

        return response;
    }
}
