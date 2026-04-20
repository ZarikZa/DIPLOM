package com.example.hhdiplom.fragments;

import android.content.Context;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.MainActivity;
import com.example.hhdiplom.R;
import com.example.hhdiplom.VacancyAdapter;
import com.example.hhdiplom.activities.LoginActivity;
import com.example.hhdiplom.activities.VacancyDetailsActivity;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.managers.ResponseManager;
import com.example.hhdiplom.models.FilterParams;
import com.example.hhdiplom.models.Vacancy;
import com.example.hhdiplom.models.VacancyResponse;
import com.google.android.material.chip.ChipGroup;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class VacanciesFragment extends Fragment {

    private static final int SEARCH_DELAY_MS = 350;

    private static final String SORT_NEWEST = "newest";
    private static final String SORT_SALARY_DESC = "salary_desc";
    private static final String SORT_SALARY_ASC = "salary_asc";
    private static final String SORT_NAME_ASC = "name_asc";

    private static final String STATE_ALL = "all";
    private static final String STATE_ACTIVE = "active";
    private static final String STATE_APPLIED = "applied";

    private ApiService apiService;

    private RecyclerView vacanciesRecyclerView;
    private EditText searchEditText;
    private ImageView filterButton;
    private Spinner spinnerVacancySort;
    private ChipGroup chipGroupVacancyState;
    private TextView tvVacancyCount;
    private ProgressBar progressBar;
    private LinearLayout emptyState;

    private VacancyAdapter vacancyAdapter;

    private final List<Vacancy> vacancyList = new ArrayList<>();
    private final List<Vacancy> filteredList = new ArrayList<>();

    private final FilterParams currentFilters = new FilterParams();
    private List<String> cities = new ArrayList<>();
    private List<String> categories = new ArrayList<>();
    private List<String> experiences = new ArrayList<>();
    private List<String> workConditions = new ArrayList<>();

    private boolean filtersLoaded = false;
    private String selectedSortKey = SORT_NEWEST;
    private String selectedStateKey = STATE_ALL;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable searchRunnable;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_vacancies, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        ApiClient.init(requireContext());
        apiService = ApiClient.getApiService();

        initViews(view);
        setupRecyclerView();
        setupSearch();
        setupSort();
        setupStateFilter();

        loadFilterData(null);
        loadVacancies();
    }

    private void initViews(View view) {
        vacanciesRecyclerView = view.findViewById(R.id.vacanciesRecyclerView);
        searchEditText = view.findViewById(R.id.searchEditText);
        filterButton = view.findViewById(R.id.filterButton);
        spinnerVacancySort = view.findViewById(R.id.spinnerVacancySort);
        chipGroupVacancyState = view.findViewById(R.id.chipGroupVacancyState);
        tvVacancyCount = view.findViewById(R.id.tvVacancyCount);
        progressBar = view.findViewById(R.id.progressBar);
        emptyState = view.findViewById(R.id.emptyState);

        filterButton.setOnClickListener(v -> {
            if (!filtersLoaded) {
                Toast.makeText(getContext(), getString(R.string.vacancies_filters_loading), Toast.LENGTH_SHORT).show();
                loadFilterData(this::showFiltersDialog);
                return;
            }
            showFiltersDialog();
        });

        updateFilterButtonState();
        updateCount();
    }

    private void setupRecyclerView() {
        vacancyAdapter = new VacancyAdapter(filteredList, new VacancyAdapter.OnVacancyClickListener() {
            @Override
            public void onVacancyClick(Vacancy vacancy) {
                showVacancyDetails(vacancy);
            }

            @Override
            public void onApplyClick(Vacancy vacancy) {
                applyForVacancy(vacancy);
            }

            @Override
            public void onVideoClick(Vacancy vacancy) {
                if (!isAdded() || getContext() == null) {
                    return;
                }
                Intent intent = new Intent(getContext(), MainActivity.class);
                intent.putExtra("vacancy_id", vacancy.getId());
                startActivity(intent);
                if (getActivity() != null) {
                    getActivity().overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                }
            }
        });

        vacanciesRecyclerView.setLayoutManager(new LinearLayoutManager(getContext()));
        vacanciesRecyclerView.setAdapter(vacancyAdapter);
    }

    private void setupSearch() {
        searchEditText.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                applyClientFiltersAndSort();
                hideKeyboard();
                return true;
            }
            return false;
        });

        searchEditText.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
            }

            @Override
            public void afterTextChanged(Editable s) {
                if (searchRunnable != null) {
                    handler.removeCallbacks(searchRunnable);
                }
                searchRunnable = VacanciesFragment.this::applyClientFiltersAndSort;
                handler.postDelayed(searchRunnable, SEARCH_DELAY_MS);
            }
        });
    }

    private void setupSort() {
        if (getContext() == null) {
            return;
        }

        List<String> sortTitles = Arrays.asList(
                getString(R.string.vacancies_sort_newest),
                getString(R.string.vacancies_sort_salary_desc),
                getString(R.string.vacancies_sort_salary_asc),
                getString(R.string.vacancies_sort_name)
        );

        ArrayAdapter<String> sortAdapter = new ArrayAdapter<>(
                requireContext(),
                android.R.layout.simple_spinner_item,
                sortTitles
        );
        sortAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerVacancySort.setAdapter(sortAdapter);

        spinnerVacancySort.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                switch (position) {
                    case 1:
                        selectedSortKey = SORT_SALARY_DESC;
                        break;
                    case 2:
                        selectedSortKey = SORT_SALARY_ASC;
                        break;
                    case 3:
                        selectedSortKey = SORT_NAME_ASC;
                        break;
                    case 0:
                    default:
                        selectedSortKey = SORT_NEWEST;
                        break;
                }
                applyClientFiltersAndSort();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
    }

    private void setupStateFilter() {
        chipGroupVacancyState.setOnCheckedChangeListener((group, checkedId) -> {
            if (checkedId == R.id.chipVacancyActive) {
                selectedStateKey = STATE_ACTIVE;
            } else if (checkedId == R.id.chipVacancyApplied) {
                selectedStateKey = STATE_APPLIED;
            } else {
                selectedStateKey = STATE_ALL;
            }
            applyClientFiltersAndSort();
        });
    }

    private void showFiltersDialog() {
        if (!isAdded() || getContext() == null) {
            return;
        }

        AlertDialog.Builder builder = new AlertDialog.Builder(getContext());
        builder.setTitle(R.string.vacancies_filters_title);

        View dialogView = getLayoutInflater().inflate(R.layout.dialog_filters, null);
        builder.setView(dialogView);

        EditText etSalaryFrom = dialogView.findViewById(R.id.etSalaryFrom);
        EditText etSalaryTo = dialogView.findViewById(R.id.etSalaryTo);

        Spinner spinnerExperience = dialogView.findViewById(R.id.spinnerExperience);
        Spinner spinnerCity = dialogView.findViewById(R.id.spinnerCity);
        Spinner spinnerCategory = dialogView.findViewById(R.id.spinnerCategory);
        Spinner spinnerWorkConditions = dialogView.findViewById(R.id.spinnerWorkConditions);

        if (currentFilters.getSalaryMin() != null) {
            etSalaryFrom.setText(String.valueOf(currentFilters.getSalaryMin()));
        }
        if (currentFilters.getSalaryMax() != null) {
            etSalaryTo.setText(String.valueOf(currentFilters.getSalaryMax()));
        }

        ArrayAdapter<String> experienceAdapter = new ArrayAdapter<>(getContext(), android.R.layout.simple_spinner_item, experiences);
        experienceAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerExperience.setAdapter(experienceAdapter);
        if (currentFilters.getExperience() != null && experiences.contains(currentFilters.getExperience())) {
            spinnerExperience.setSelection(experiences.indexOf(currentFilters.getExperience()));
        }

        ArrayAdapter<String> cityAdapter = new ArrayAdapter<>(getContext(), android.R.layout.simple_spinner_item, cities);
        cityAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerCity.setAdapter(cityAdapter);
        if (currentFilters.getCity() != null && cities.contains(currentFilters.getCity())) {
            spinnerCity.setSelection(cities.indexOf(currentFilters.getCity()));
        }

        ArrayAdapter<String> categoryAdapter = new ArrayAdapter<>(getContext(), android.R.layout.simple_spinner_item, categories);
        categoryAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerCategory.setAdapter(categoryAdapter);
        if (currentFilters.getCategory() != null && categories.contains(currentFilters.getCategory())) {
            spinnerCategory.setSelection(categories.indexOf(currentFilters.getCategory()));
        }

        ArrayAdapter<String> workAdapter = new ArrayAdapter<>(getContext(), android.R.layout.simple_spinner_item, workConditions);
        workAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerWorkConditions.setAdapter(workAdapter);
        if (currentFilters.getWorkConditions() != null && workConditions.contains(currentFilters.getWorkConditions())) {
            spinnerWorkConditions.setSelection(workConditions.indexOf(currentFilters.getWorkConditions()));
        }

        builder.setPositiveButton(R.string.apply, (dialog, which) -> {
            currentFilters.setSalaryMin(parseIntegerOrNull(etSalaryFrom.getText() != null ? etSalaryFrom.getText().toString() : null));
            currentFilters.setSalaryMax(parseIntegerOrNull(etSalaryTo.getText() != null ? etSalaryTo.getText().toString() : null));
            currentFilters.setExperience(getSpinnerValueOrNull(spinnerExperience));
            currentFilters.setCity(getSpinnerValueOrNull(spinnerCity));
            currentFilters.setCategory(getSpinnerValueOrNull(spinnerCategory));
            currentFilters.setWorkConditions(getSpinnerValueOrNull(spinnerWorkConditions));
            applyFilters();
        });

        builder.setNegativeButton(R.string.reset, (dialog, which) -> {
            currentFilters.clear();
            applyFilters();
        });

        builder.setNeutralButton(R.string.cancel, null);
        builder.show();
    }

    private String getSpinnerValueOrNull(Spinner spinner) {
        if (spinner == null || spinner.getSelectedItem() == null) {
            return null;
        }
        String value = spinner.getSelectedItem().toString();
        return value.trim().isEmpty() ? null : value;
    }

    private Integer parseIntegerOrNull(String value) {
        if (value == null) {
            return null;
        }
        String raw = value.trim();
        if (raw.isEmpty()) {
            return null;
        }
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private void applyFilters() {
        updateFilterButtonState();
        loadVacancies();
    }

    private void updateFilterButtonState() {
        int activeFilters = 0;
        if (currentFilters.getCity() != null) activeFilters++;
        if (currentFilters.getCategory() != null) activeFilters++;
        if (currentFilters.getExperience() != null) activeFilters++;
        if (currentFilters.getWorkConditions() != null) activeFilters++;
        if (currentFilters.getSalaryMin() != null) activeFilters++;
        if (currentFilters.getSalaryMax() != null) activeFilters++;
        if (currentFilters.isOnlyFavorites()) activeFilters++;

        if (!isAdded()) {
            return;
        }

        int tintColor = activeFilters > 0
                ? ContextCompat.getColor(requireContext(), R.color.primary)
                : ContextCompat.getColor(requireContext(), R.color.dark_gray);
        filterButton.setImageTintList(ColorStateList.valueOf(tintColor));
        filterButton.setContentDescription(activeFilters > 0
                ? getString(R.string.vacancies_filters_desc_selected, activeFilters)
                : getString(R.string.vacancies_filters_desc));
    }

    private void loadFilterData(Runnable onLoaded) {
        cities = Arrays.asList("Москва", "Санкт-Петербург", "Казань");
        categories = Arrays.asList("IT", "Маркетинг", "Продажи", "HR");
        experiences = Arrays.asList("Без опыта", "1-3 года", "3-6 лет", "от 6 лет");

        apiService.getWorkConditions().enqueue(new Callback<List<String>>() {
            @Override
            public void onResponse(Call<List<String>> call, Response<List<String>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    workConditions = response.body();
                }
                filtersLoaded = true;
                if (onLoaded != null && isAdded() && getActivity() != null) {
                    getActivity().runOnUiThread(onLoaded);
                }
            }

            @Override
            public void onFailure(Call<List<String>> call, Throwable t) {
                filtersLoaded = true;
                if (onLoaded != null && isAdded() && getActivity() != null) {
                    getActivity().runOnUiThread(onLoaded);
                }
            }
        });
    }

    private void loadVacancies() {
        if (!ApiClient.isLoggedIn() || !isAdded() || getContext() == null) {
            return;
        }

        progressBar.setVisibility(View.VISIBLE);
        emptyState.setVisibility(View.GONE);

        String searchQuery = searchEditText.getText().toString().trim();
        String city = currentFilters.getCity();
        String category = currentFilters.getCategory();
        String experience = currentFilters.getExperience();
        String workConditionsFilter = currentFilters.getWorkConditions();
        Integer salaryMin = currentFilters.getSalaryMin();
        Integer salaryMax = currentFilters.getSalaryMax();
        Boolean onlyFavorites = currentFilters.getOnlyFavoritesQuery();
        String userType = ApiClient.getUserType();

        boolean hasServerFilters =
                city != null
                        || category != null
                        || experience != null
                        || workConditionsFilter != null
                        || salaryMin != null
                        || salaryMax != null
                        || Boolean.TRUE.equals(onlyFavorites);

        boolean isApplicant = userType != null && "applicant".equalsIgnoreCase(userType.trim());
        Boolean useRecommended = (isApplicant && searchQuery.isEmpty() && !hasServerFilters)
                ? Boolean.TRUE
                : null;

        Call<VacancyResponse> call = apiService.getVacancies(
                searchQuery.isEmpty() ? null : searchQuery,
                city,
                category,
                experience,
                workConditionsFilter,
                salaryMin,
                salaryMax,
                onlyFavorites,
                useRecommended,
                1
        );

        call.enqueue(new Callback<VacancyResponse>() {
            @Override
            public void onResponse(Call<VacancyResponse> call, Response<VacancyResponse> response) {
                if (!isAdded() || getActivity() == null) {
                    return;
                }

                getActivity().runOnUiThread(() -> {
                    progressBar.setVisibility(View.GONE);

                    if (response.isSuccessful() && response.body() != null) {
                        vacancyList.clear();
                        if (response.body().getResults() != null) {
                            vacancyList.addAll(response.body().getResults());
                        }
                        applyClientFiltersAndSort();
                    } else {
                        handleErrorResponse(response.code());
                    }
                });
            }

            @Override
            public void onFailure(Call<VacancyResponse> call, Throwable t) {
                if (!isAdded() || getActivity() == null) {
                    return;
                }

                getActivity().runOnUiThread(() -> {
                    progressBar.setVisibility(View.GONE);
                    if (getContext() != null) {
                        Toast.makeText(
                                getContext(),
                                getString(R.string.vacancies_error_connection, t.getMessage()),
                                Toast.LENGTH_SHORT
                        ).show();
                    }
                    filteredList.clear();
                    vacancyAdapter.updateList(filteredList);
                    updateEmptyState();
                    updateCount();
                });
            }
        });
    }

    private void applyClientFiltersAndSort() {
        String query = searchEditText.getText().toString().trim().toLowerCase(Locale.getDefault());

        List<Vacancy> prepared = new ArrayList<>();
        for (Vacancy vacancy : vacancyList) {
            if (!matchesSearch(vacancy, query)) {
                continue;
            }
            if (!matchesState(vacancy)) {
                continue;
            }
            prepared.add(vacancy);
        }

        sortVacancies(prepared);

        filteredList.clear();
        filteredList.addAll(prepared);

        vacancyAdapter.updateList(filteredList);
        updateEmptyState();
        updateCount();
    }

    private boolean matchesSearch(Vacancy vacancy, String query) {
        if (query == null || query.isEmpty()) {
            return true;
        }
        return contains(vacancy.getPosition(), query)
                || contains(vacancy.getCompanyName(), query)
                || contains(vacancy.getCity(), query)
                || contains(vacancy.getCategory(), query)
                || contains(vacancy.getExperience(), query);
    }

    private boolean contains(String source, String query) {
        if (source == null) {
            return false;
        }
        return source.toLowerCase(Locale.getDefault()).contains(query);
    }

    private boolean matchesState(Vacancy vacancy) {
        if (STATE_APPLIED.equals(selectedStateKey)) {
            return vacancy.isHasApplied();
        }

        if (STATE_ACTIVE.equals(selectedStateKey)) {
            return !vacancy.isHasApplied() && isVacancyActive(vacancy.getStatusName());
        }

        return true;
    }

    private boolean isVacancyActive(String statusName) {
        if (statusName == null || statusName.trim().isEmpty()) {
            return true;
        }

        String normalized = statusName.toLowerCase(Locale.getDefault());
        if (normalized.contains("closed")
                || normalized.contains("archive")
                || normalized.contains("inactive")
                || normalized.contains("\u0437\u0430\u043a\u0440\u044b")
                || normalized.contains("\u0430\u0440\u0445\u0438\u0432")) {
            return false;
        }
        if (normalized.contains("open")
                || normalized.contains("active")
                || normalized.contains("\u043e\u0442\u043a\u0440")
                || normalized.contains("\u0430\u043a\u0442\u0438\u0432")) {
            return true;
        }

        return true;
    }

    private void sortVacancies(List<Vacancy> list) {
        Comparator<Vacancy> comparator;
        switch (selectedSortKey) {
            case SORT_SALARY_DESC:
                comparator = (left, right) -> Integer.compare(getVacancySalary(right), getVacancySalary(left));
                break;
            case SORT_SALARY_ASC:
                comparator = Comparator.comparingInt(this::getVacancySalary);
                break;
            case SORT_NAME_ASC:
                comparator = (left, right) -> safeString(left.getPosition()).compareToIgnoreCase(safeString(right.getPosition()));
                break;
            case SORT_NEWEST:
            default:
                comparator = (left, right) -> Long.compare(parseDate(right.getCreatedDate()), parseDate(left.getCreatedDate()));
                break;
        }
        Collections.sort(list, comparator);
    }

    private int getVacancySalary(Vacancy vacancy) {
        int max = parseMoney(vacancy.getSalaryMax());
        int min = parseMoney(vacancy.getSalaryMin());
        return Math.max(max, min);
    }

    private int parseMoney(String value) {
        if (value == null) {
            return 0;
        }
        String digits = value.replaceAll("[^0-9]", "");
        if (digits.isEmpty()) {
            return 0;
        }
        try {
            return Integer.parseInt(digits);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private long parseDate(String dateText) {
        if (dateText == null || dateText.trim().isEmpty()) {
            return 0L;
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
                SimpleDateFormat format = new SimpleDateFormat(pattern, Locale.US);
                Date parsed = format.parse(dateText);
                if (parsed != null) {
                    return parsed.getTime();
                }
            } catch (ParseException ignored) {
            }
        }

        return 0L;
    }

    private String safeString(String value) {
        return value == null ? "" : value;
    }

    private void updateCount() {
        tvVacancyCount.setText(getString(R.string.vacancies_count, filteredList.size()));
    }

    private void updateEmptyState() {
        if (filteredList.isEmpty()) {
            emptyState.setVisibility(View.VISIBLE);
            vacanciesRecyclerView.setVisibility(View.GONE);
        } else {
            emptyState.setVisibility(View.GONE);
            vacanciesRecyclerView.setVisibility(View.VISIBLE);
        }
    }

    private void handleErrorResponse(int code) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        switch (code) {
            case 401:
                Toast.makeText(getContext(), getString(R.string.session_expired_login_again), Toast.LENGTH_LONG).show();
                ApiClient.clearTokens();
                startActivity(new Intent(getContext(), LoginActivity.class));
                if (getActivity() != null) {
                    getActivity().finish();
                }
                break;
            default:
                Toast.makeText(getContext(), getString(R.string.error_with_code, code), Toast.LENGTH_SHORT).show();
                break;
        }

        filteredList.clear();
        vacancyAdapter.updateList(filteredList);
        updateEmptyState();
        updateCount();
    }

    private void showVacancyDetails(Vacancy vacancy) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        ResponseManager.checkIfResponded(getContext(), vacancy.getId(), new ResponseManager.ResponseCallback() {
            @Override
            public void onSuccess(int responseId) {
                openVacancyDetails(vacancy.getId());
            }

            @Override
            public void onFailure(String error) {
                if (isAdded() && getActivity() != null) {
                    getActivity().runOnUiThread(() -> openVacancyDetails(vacancy.getId()));
                }
            }
        });
    }

    private void openVacancyDetails(int vacancyId) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        Intent intent = new Intent(getContext(), VacancyDetailsActivity.class);
        intent.putExtra("vacancy_id", vacancyId);
        startActivity(intent);
        if (getActivity() != null) {
            getActivity().overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }

    private void applyForVacancy(Vacancy vacancy) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        if (vacancy.isHasApplied()) {
            Toast.makeText(getContext(), getString(R.string.vacancies_apply_already), Toast.LENGTH_SHORT).show();
            return;
        }

        ResponseManager.showResponseDialog(
                getContext(),
                vacancy.getPosition(),
                vacancy.getCompanyName(),
                vacancy.getId(),
                new ResponseManager.ResponseCallback() {
                    @Override
                    public void onSuccess(int responseId) {
                        if (!isAdded() || getActivity() == null) {
                            return;
                        }

                        getActivity().runOnUiThread(() -> {
                            vacancy.setHasApplied(true);
                            applyClientFiltersAndSort();
                            Toast.makeText(getContext(), getString(R.string.vacancies_apply_success), Toast.LENGTH_SHORT).show();
                        });
                    }

                    @Override
                    public void onFailure(String error) {
                        if (!isAdded() || getActivity() == null) {
                            return;
                        }

                        if ("already_responded".equals(error)) {
                            getActivity().runOnUiThread(() ->
                                    Toast.makeText(getContext(), getString(R.string.vacancies_apply_already), Toast.LENGTH_SHORT).show());
                        }
                    }
                }
        );
    }

    private void hideKeyboard() {
        if (!isAdded() || getContext() == null) {
            return;
        }

        InputMethodManager imm = (InputMethodManager) getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null) {
            imm.hideSoftInputFromWindow(searchEditText.getWindowToken(), 0);
        }
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        if (searchRunnable != null) {
            handler.removeCallbacks(searchRunnable);
        }
    }

    public void refreshVacancies() {
        loadVacancies();
    }
}
