package com.example.hhdiplom.activities;

import android.content.Context;
import android.content.res.TypedArray;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.CmProfileStatsResponse;

import java.util.List;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class CmAnalyticsActivity extends AppCompatActivity {
    private TextView tvManagerName;
    private TextView tvManagerMeta;
    private TextView tvCompanyName;
    private TextView tvCompanyMeta;

    private LinearLayout statsContainer;
    private LinearLayout chartContainer;
    private LinearLayout statusContainer;
    private LinearLayout topVacanciesContainer;

    private ProgressBar progressBar;

    private ApiService apiService;
    private Call<CmProfileStatsResponse> statsCall;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cm_analytics);

        apiService = ApiClient.getApiService();

        ImageButton btnBack = findViewById(R.id.btnBack);
        tvManagerName = findViewById(R.id.tvManagerName);
        tvManagerMeta = findViewById(R.id.tvManagerMeta);
        tvCompanyName = findViewById(R.id.tvCompanyName);
        tvCompanyMeta = findViewById(R.id.tvCompanyMeta);

        statsContainer = findViewById(R.id.statsContainer);
        chartContainer = findViewById(R.id.chartContainer);
        statusContainer = findViewById(R.id.statusContainer);
        topVacanciesContainer = findViewById(R.id.topVacanciesContainer);

        progressBar = findViewById(R.id.progressBar);

        btnBack.setOnClickListener(v -> finish());

        loadAnalytics();
    }

    private void loadAnalytics() {
        progressBar.setVisibility(View.VISIBLE);

        statsCall = apiService.getCmProfileStats();
        statsCall.enqueue(new Callback<CmProfileStatsResponse>() {
            @Override
            public void onResponse(Call<CmProfileStatsResponse> call, Response<CmProfileStatsResponse> response) {
                progressBar.setVisibility(View.GONE);

                if (response.isSuccessful() && response.body() != null) {
                    bindAnalytics(response.body());
                } else {
                    Toast.makeText(CmAnalyticsActivity.this, getString(R.string.cm_analytics_load_failed), Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onFailure(Call<CmProfileStatsResponse> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                Toast.makeText(CmAnalyticsActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_LONG).show();
            }
        });
    }

    private void bindAnalytics(CmProfileStatsResponse data) {
        String fallback = getString(R.string.profile_not_specified);

        if (data.getManager() != null) {
            tvManagerName.setText(nonEmpty(data.getManager().getFullName(), getString(R.string.cm_analytics_manager_fallback)));
            tvManagerMeta.setText(getString(
                    R.string.cm_analytics_manager_meta_template,
                    getString(R.string.cm_analytics_role_label),
                    nonEmpty(data.getManager().getRole(), fallback),
                    nonEmpty(data.getManager().getEmail(), fallback),
                    getString(R.string.cm_analytics_phone_label),
                    nonEmpty(data.getManager().getPhone(), fallback)
            ));
        }

        if (data.getCompany() != null) {
            tvCompanyName.setText(nonEmpty(data.getCompany().getName(), getString(R.string.cm_analytics_company_fallback)));
            tvCompanyMeta.setText(getString(
                    R.string.cm_analytics_company_meta_template,
                    getString(R.string.cm_analytics_number_label),
                    nonEmpty(data.getCompany().getNumber(), fallback),
                    getString(R.string.cm_analytics_industry_label),
                    nonEmpty(data.getCompany().getIndustry(), fallback),
                    nonEmpty(data.getCompany().getDescription(), getString(R.string.cm_analytics_company_description_fallback))
            ));
        }

        statsContainer.removeAllViews();
        if (data.getStats() != null) {
            addStatRow(statsContainer, getString(R.string.cm_analytics_stat_videos), data.getStats().getVideosCount());
            addStatRow(statsContainer, getString(R.string.cm_analytics_stat_vacancies), data.getStats().getVacanciesCount());
            addStatRow(statsContainer, getString(R.string.cm_analytics_stat_responses), data.getStats().getResponsesCount());
            addStatRow(statsContainer, getString(R.string.cm_analytics_stat_video_views), data.getStats().getVideoViewsCount());
            addStatRow(statsContainer, getString(R.string.cm_analytics_stat_video_likes), data.getStats().getVideoLikesCount());
            addStatRow(statsContainer, getString(R.string.cm_analytics_stat_vacancy_views), data.getStats().getVacancyViewsCount());
        }

        renderChart(data.getChart(), data.getStats());
        renderResponsesByStatus(data.getResponsesByStatus());
        renderTopVacancies(data.getTopVacancies());
    }

    private void renderChart(CmProfileStatsResponse.ChartInfo chartInfo, CmProfileStatsResponse.StatsInfo statsInfo) {
        chartContainer.removeAllViews();
        List<String> labels = null;
        List<Integer> values = null;

        if (chartInfo != null) {
            labels = chartInfo.getLabels();
            values = chartInfo.getValues();
        }

        if (labels == null || values == null || labels.isEmpty() || values.isEmpty()) {
            if (statsInfo != null) {
                labels = java.util.Arrays.asList(
                        getString(R.string.cm_analytics_stat_videos),
                        getString(R.string.cm_analytics_stat_vacancies),
                        getString(R.string.cm_analytics_stat_responses),
                        getString(R.string.cm_analytics_stat_video_views),
                        getString(R.string.cm_analytics_stat_video_likes)
                );
                values = java.util.Arrays.asList(
                        statsInfo.getVideosCount(),
                        statsInfo.getVacanciesCount(),
                        statsInfo.getResponsesCount(),
                        statsInfo.getVideoViewsCount(),
                        statsInfo.getVideoLikesCount()
                );
            } else {
                addEmptyText(chartContainer, getString(R.string.cm_analytics_no_chart_data));
                return;
            }
        }

        if (labels.isEmpty() || values.isEmpty()) {
            addEmptyText(chartContainer, getString(R.string.cm_analytics_no_chart_data));
            return;
        }

        int maxValue = 1;
        for (Integer value : values) {
            if (value != null && value > maxValue) {
                maxValue = value;
            }
        }

        for (int i = 0; i < labels.size() && i < values.size(); i++) {
            String label = labels.get(i);
            int value = values.get(i) == null ? 0 : values.get(i);

            TextView title = new TextView(this);
            title.setText(label + ": " + value);
            title.setTextColor(resolveAttrColor(this, R.attr.colorTextPrimary));
            title.setTextSize(13f);

            ProgressBar bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            bar.setMax(maxValue);
            bar.setProgress(value);
            bar.setProgressTintList(android.content.res.ColorStateList.valueOf(
                    ContextCompat.getColor(this, R.color.primary)
            ));

            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(0, 0, 0, 14);
            row.addView(title);
            row.addView(bar, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
            ));

            chartContainer.addView(row);
        }
    }

    private void renderResponsesByStatus(List<CmProfileStatsResponse.ResponseStatusItem> items) {
        statusContainer.removeAllViews();
        if (items == null || items.isEmpty()) {
            addEmptyText(statusContainer, getString(R.string.cm_analytics_status_empty));
            return;
        }

        for (CmProfileStatsResponse.ResponseStatusItem item : items) {
            addStatusRow(statusContainer, nonEmpty(item.getStatus(), getString(R.string.cm_analytics_status_fallback)), item.getCount());
        }
    }

    private void renderTopVacancies(List<CmProfileStatsResponse.TopVacancyItem> items) {
        topVacanciesContainer.removeAllViews();
        if (items == null || items.isEmpty()) {
            addEmptyText(topVacanciesContainer, getString(R.string.cm_analytics_top_empty));
            return;
        }

        int rank = 1;
        for (CmProfileStatsResponse.TopVacancyItem item : items) {
            TextView row = new TextView(this);
            row.setText(getString(
                    R.string.cm_analytics_top_row,
                    rank,
                    nonEmpty(item.getPosition(), getString(R.string.cm_analytics_vacancy_fallback)),
                    item.getResponsesCount(),
                    getString(R.string.cm_analytics_responses_word)
            ));
            row.setTextColor(resolveAttrColor(this, R.attr.colorTextPrimary));
            row.setTextSize(14f);
            row.setPadding(0, 0, 0, 10);
            topVacanciesContainer.addView(row);
            rank++;
        }
    }

    private void addStatRow(LinearLayout target, String title, int value) {
        View row = getLayoutInflater().inflate(R.layout.item_stat, target, false);
        TextView tvTitle = row.findViewById(R.id.tvStatTitle);
        TextView tvValue = row.findViewById(R.id.tvStatValue);
        tvTitle.setText(title);
        tvValue.setText(String.valueOf(value));
        target.addView(row);
    }

    private void addStatusRow(LinearLayout target, String status, int count) {
        View row = getLayoutInflater().inflate(R.layout.item_stat, target, false);
        TextView tvTitle = row.findViewById(R.id.tvStatTitle);
        TextView tvValue = row.findViewById(R.id.tvStatValue);
        tvTitle.setText(status);
        tvValue.setText(String.valueOf(count));
        target.addView(row);
    }

    private void addEmptyText(LinearLayout target, String text) {
        TextView empty = new TextView(this);
        empty.setText(text);
        empty.setTextColor(resolveAttrColor(this, R.attr.colorTextSecondary));
        empty.setTextSize(14f);
        empty.setPadding(0, 0, 0, 8);
        target.addView(empty);
    }

    private String nonEmpty(String value, String fallback) {
        return TextUtils.isEmpty(value) ? fallback : value;
    }

    private int resolveAttrColor(Context context, int attrId) {
        TypedArray ta = context.obtainStyledAttributes(new int[]{attrId});
        int color = ta.getColor(0, ContextCompat.getColor(context, R.color.on_surface));
        ta.recycle();
        return color;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (statsCall != null && !statsCall.isCanceled()) {
            statsCall.cancel();
        }
    }
}
