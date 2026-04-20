package com.example.hhdiplom.adapters;

import android.content.Context;
import android.text.TextUtils;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.ResponseItem;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class ResponsesAdapter extends RecyclerView.Adapter<ResponsesAdapter.ViewHolder> {

    private List<ResponseItem> responseList;
    private final OnResponseClickListener listener;

    public interface OnResponseClickListener {
        void onResponseClick(ResponseItem response);
    }

    public ResponsesAdapter(List<ResponseItem> responseList, OnResponseClickListener listener) {
        this.responseList = responseList;
        this.listener = listener;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_response, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        ResponseItem response = responseList.get(position);
        Context context = holder.itemView.getContext();

        holder.tvPosition.setText(safeValue(response.getVacancyPosition(), context.getString(R.string.response_no_vacancy)));
        holder.tvCompany.setText(safeValue(response.getCompanyName(), context.getString(R.string.response_no_company)));
        holder.tvStatus.setText(safeValue(response.getStatusName(), context.getString(R.string.response_status_sent)));
        holder.tvDate.setText(formatDate(context, response.getResponseDate()));

        StatusStyle style = getStatusStyle(response.getStatusName());
        holder.tvStatus.setBackgroundResource(style.backgroundRes);
        holder.tvStatus.setTextColor(ContextCompat.getColor(context, style.textColorRes));

        holder.itemView.setOnClickListener(v -> {
            if (listener != null) {
                listener.onResponseClick(response);
            }
        });
    }

    @Override
    public int getItemCount() {
        return responseList == null ? 0 : responseList.size();
    }

    public void updateList(List<ResponseItem> newList) {
        this.responseList = new ArrayList<>(newList);
        notifyDataSetChanged();
    }

    private String safeValue(String value, String fallback) {
        return TextUtils.isEmpty(value) ? fallback : value;
    }

    private String formatDate(Context context, String rawDate) {
        if (TextUtils.isEmpty(rawDate)) {
            return context.getString(R.string.response_date_unknown);
        }

        List<String> patterns = Arrays.asList(
                "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
                "yyyy-MM-dd'T'HH:mm:ssXXX",
                "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
                "yyyy-MM-dd'T'HH:mm:ss'Z'",
                "yyyy-MM-dd'T'HH:mm:ss"
        );

        for (String pattern : patterns) {
            try {
                SimpleDateFormat parser = new SimpleDateFormat(pattern, Locale.US);
                Date date = parser.parse(rawDate);
                if (date != null) {
                    SimpleDateFormat display = new SimpleDateFormat("dd.MM.yyyy", Locale.getDefault());
                    return display.format(date);
                }
            } catch (ParseException ignored) {
            }
        }

        return rawDate;
    }

    private StatusStyle getStatusStyle(String rawStatus) {
        String status = rawStatus == null ? "" : rawStatus.toLowerCase(Locale.getDefault());

        if (status.contains("invite")
                || status.contains("priglash")
                || status.contains("\u043f\u0440\u0438\u0433\u043b\u0430\u0448")) {
            return new StatusStyle(R.drawable.bg_status_success, R.color.status_success_text);
        }

        if (status.contains("reject")
                || status.contains("otkaz")
                || status.contains("\u043e\u0442\u043a\u0430\u0437")) {
            return new StatusStyle(R.drawable.bg_status_error, R.color.status_error_text);
        }

        if (status.contains("progress")
                || status.contains("review")
                || status.contains("interview")
                || status.contains("process")
                || status.contains("\u043f\u0440\u043e\u0446\u0435\u0441\u0441")
                || status.contains("\u0440\u0430\u0441\u0441\u043c\u043e\u0442\u0440")
                || status.contains("\u0438\u043d\u0442\u0435\u0440\u0432\u044c\u044e")) {
            return new StatusStyle(R.drawable.bg_status_warning, R.color.status_warning_text);
        }

        if (status.contains("sent")
                || status.contains("new")
                || status.contains("otprav")
                || status.contains("\u043e\u0442\u043f\u0440\u0430\u0432")) {
            return new StatusStyle(R.drawable.bg_status_info, R.color.status_info_text);
        }

        return new StatusStyle(R.drawable.bg_status_neutral, R.color.status_neutral_text);
    }

    static class ViewHolder extends RecyclerView.ViewHolder {
        final TextView tvPosition;
        final TextView tvCompany;
        final TextView tvStatus;
        final TextView tvDate;

        ViewHolder(@NonNull View itemView) {
            super(itemView);
            tvPosition = itemView.findViewById(R.id.tvPosition);
            tvCompany = itemView.findViewById(R.id.tvCompany);
            tvStatus = itemView.findViewById(R.id.tvStatus);
            tvDate = itemView.findViewById(R.id.tvDate);
        }
    }

    private static class StatusStyle {
        final int backgroundRes;
        final int textColorRes;

        StatusStyle(int backgroundRes, int textColorRes) {
            this.backgroundRes = backgroundRes;
            this.textColorRes = textColorRes;
        }
    }
}
