package com.example.hhdiplom;

import android.text.TextUtils;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.models.Vacancy;

import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.List;
import java.util.Locale;

public class VacancyAdapter extends RecyclerView.Adapter<VacancyAdapter.VacancyViewHolder> {

    private List<Vacancy> vacancyList;
    private final OnVacancyClickListener listener;

    public interface OnVacancyClickListener {
        void onVacancyClick(Vacancy vacancy);

        void onApplyClick(Vacancy vacancy);

        void onVideoClick(Vacancy vacancy);
    }

    public VacancyAdapter(List<Vacancy> vacancyList, OnVacancyClickListener listener) {
        this.vacancyList = vacancyList;
        this.listener = listener;
    }

    public void updateList(List<Vacancy> newList) {
        this.vacancyList = newList;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public VacancyViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_vacancy, parent, false);
        return new VacancyViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull VacancyViewHolder holder, int position) {
        Vacancy vacancy = vacancyList.get(position);
        holder.bind(vacancy, listener);
    }

    @Override
    public int getItemCount() {
        return vacancyList == null ? 0 : vacancyList.size();
    }

    static class VacancyViewHolder extends RecyclerView.ViewHolder {
        private final TextView positionTextView;
        private final TextView companyTextView;
        private final TextView salaryTextView;
        private final TextView cityTextView;
        private final TextView experienceTextView;
        private final TextView statusBadge;
        private final Button applyButton;
        private final Button videoButton;

        VacancyViewHolder(@NonNull View itemView) {
            super(itemView);
            positionTextView = itemView.findViewById(R.id.positionTextView);
            companyTextView = itemView.findViewById(R.id.companyTextView);
            salaryTextView = itemView.findViewById(R.id.salaryTextView);
            cityTextView = itemView.findViewById(R.id.cityTextView);
            experienceTextView = itemView.findViewById(R.id.experienceTextView);
            statusBadge = itemView.findViewById(R.id.statusBadge);
            applyButton = itemView.findViewById(R.id.applyButton);
            videoButton = itemView.findViewById(R.id.videoButton);
        }

        void bind(Vacancy vacancy, OnVacancyClickListener listener) {
            positionTextView.setText(safeValue(vacancy.getPosition(), str(R.string.vacancy_no_title)));
            companyTextView.setText(safeValue(vacancy.getCompanyName(), str(R.string.vacancy_no_company)));
            cityTextView.setText(safeValue(vacancy.getCity(), str(R.string.vacancy_no_city)));
            experienceTextView.setText(safeValue(vacancy.getExperience(), str(R.string.vacancy_no_experience)));
            salaryTextView.setText(formatSalary(vacancy));

            bindStatus(vacancy);

            String userType = ApiClient.getUserType();
            if ("content_manager".equals(userType)) {
                bindForContentManager(vacancy, listener);
            } else {
                bindForApplicant(vacancy, listener);
            }

            itemView.setOnClickListener(v -> {
                if (listener != null) {
                    listener.onVacancyClick(vacancy);
                }
            });
        }

        private void bindForContentManager(Vacancy vacancy, OnVacancyClickListener listener) {
            videoButton.setVisibility(View.VISIBLE);
            applyButton.setVisibility(View.GONE);
            videoButton.setEnabled(true);

            videoButton.setText(vacancy.hasVideo()
                    ? str(R.string.vacancy_video_edit)
                    : str(R.string.vacancy_video_add));
            videoButton.setOnClickListener(v -> {
                if (listener != null) {
                    listener.onVideoClick(vacancy);
                }
            });
        }

        private void bindForApplicant(Vacancy vacancy, OnVacancyClickListener listener) {
            videoButton.setVisibility(View.GONE);
            applyButton.setVisibility(View.VISIBLE);

            if (vacancy.isHasApplied()) {
                applyButton.setText(str(R.string.vacancy_applied_button));
                applyButton.setBackgroundResource(R.drawable.bg_apply_done_button);
                applyButton.setTextColor(ContextCompat.getColor(itemView.getContext(), R.color.white));
                applyButton.setEnabled(false);
            } else {
                applyButton.setText(str(R.string.vacancy_apply_button));
                applyButton.setBackgroundResource(R.drawable.bg_apply_button);
                applyButton.setTextColor(ContextCompat.getColor(itemView.getContext(), R.color.white));
                applyButton.setEnabled(true);
            }

            applyButton.setOnClickListener(v -> {
                if (!vacancy.isHasApplied() && listener != null) {
                    listener.onApplyClick(vacancy);
                }
            });
        }

        private void bindStatus(Vacancy vacancy) {
            if (vacancy.isHasApplied()) {
                statusBadge.setText(str(R.string.vacancy_status_applied));
                statusBadge.setBackgroundResource(R.drawable.bg_status_success);
                statusBadge.setTextColor(ContextCompat.getColor(itemView.getContext(), R.color.status_success_text));
                return;
            }

            String status = safeValue(vacancy.getStatusName(), str(R.string.vacancy_status_active));
            String normalized = status.toLowerCase(Locale.getDefault());

            if (isClosed(normalized)) {
                statusBadge.setText(status);
                statusBadge.setBackgroundResource(R.drawable.bg_status_neutral);
                statusBadge.setTextColor(ContextCompat.getColor(itemView.getContext(), R.color.status_neutral_text));
                return;
            }

            statusBadge.setText(status);
            statusBadge.setBackgroundResource(R.drawable.bg_status_info);
            statusBadge.setTextColor(ContextCompat.getColor(itemView.getContext(), R.color.status_info_text));
        }

        private boolean isClosed(String normalizedStatus) {
            return normalizedStatus.contains("closed")
                    || normalizedStatus.contains("archive")
                    || normalizedStatus.contains("inactive")
                    || normalizedStatus.contains("zakr")
                    || normalizedStatus.contains("arhiv")
                    || normalizedStatus.contains("\u0437\u0430\u043a\u0440\u044b")
                    || normalizedStatus.contains("\u0430\u0440\u0445\u0438\u0432");
        }

        private String safeValue(String value, String fallback) {
            return TextUtils.isEmpty(value) ? fallback : value;
        }

        private String formatSalary(Vacancy vacancy) {
            Integer min = parseSalary(vacancy.getSalaryMin());
            Integer max = parseSalary(vacancy.getSalaryMax());

            if (min != null && max != null) {
                return str(R.string.vacancy_salary_range, formatMoney(min), formatMoney(max));
            }
            if (min != null) {
                return str(R.string.vacancy_salary_from, formatMoney(min));
            }
            if (max != null) {
                return str(R.string.vacancy_salary_to, formatMoney(max));
            }
            return str(R.string.vacancy_salary_unknown);
        }

        private Integer parseSalary(String raw) {
            if (TextUtils.isEmpty(raw)) {
                return null;
            }
            String cleaned = raw.replace(',', '.').trim();
            try {
                double value = Double.parseDouble(cleaned);
                return (int) Math.round(value);
            } catch (NumberFormatException ignored) {
            }

            String digits = cleaned.replaceAll("[^0-9]", "");
            if (digits.isEmpty()) {
                return null;
            }
            try {
                return Integer.parseInt(digits);
            } catch (NumberFormatException ignored) {
                return null;
            }
        }

        private String formatMoney(int value) {
            DecimalFormatSymbols symbols = new DecimalFormatSymbols(Locale.US);
            symbols.setGroupingSeparator(' ');
            DecimalFormat formatter = new DecimalFormat("###,###", symbols);
            return formatter.format(value) + " руб.";
        }

        private String str(int resId, Object... args) {
            return itemView.getContext().getString(resId, args);
        }
    }
}
