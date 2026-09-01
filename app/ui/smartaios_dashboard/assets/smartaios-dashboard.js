(() => {
  "use strict";

  const REFRESH_INTERVAL_MS = 30_000;
  const HEARTBEAT_INTERVAL_MS = 30_000;
  const LOG_PAGE_SIZE = 25;
  const SESSION_STORAGE_KEY = "smartaios.analytics.session_id";

  const state = {
    dashboard: null,
    identity: null,
    logs: [],
    logType: "all",
    logSearch: "",
    logPage: 1,
    requestController: null,
    lastLoadedAt: 0,
  };

  const byId = id => document.getElementById(id);
  const dashboardFilters = byId("dashboardFilters");
  const daysFilter = byId("daysFilter");
  const applicationFilter = byId("applicationFilter");
  const actorFilter = byId("actorFilter");
  const statusFilter = byId("statusFilter");
  const refreshButton = byId("refreshButton");
  const refreshState = byId("refreshState");
  const dataTimestamp = byId("dataTimestamp");

  const totalOperations = byId("totalOperations");
  const totalOperationsNote = byId("totalOperationsNote");
  const successfulOperations = byId("successfulOperations");
  const successRate = byId("successRate");
  const failedOperations = byId("failedOperations");
  const failureRate = byId("failureRate");
  const runningOperations = byId("runningOperations");
  const activeUsers = byId("activeUsers");
  const knownUsers = byId("knownUsers");
  const activeUsage = byId("activeUsage");
  const processingTime = byId("processingTime");

  const trendChart = byId("trendChart");
  const resultRing = byId("resultRing");
  const resultRingValue = byId("resultRingValue");
  const resultSuccessCount = byId("resultSuccessCount");
  const resultFailedCount = byId("resultFailedCount");
  const resultOtherCount = byId("resultOtherCount");
  const usersTableBody = byId("usersTableBody");
  const usersMeta = byId("usersMeta");
  const applicationGroups = byId("applicationGroups");
  const applicationsMeta = byId("applicationsMeta");
  const runningJobsList = byId("runningJobsList");
  const notificationsList = byId("notificationsList");
  const notificationsMeta = byId("notificationsMeta");

  const logSearch = byId("logSearch");
  const logTabs = Array.from(document.querySelectorAll("[data-log-type]"));
  const logsTableBody = byId("logsTableBody");
  const logsMeta = byId("logsMeta");
  const logsPage = byId("logsPage");
  const previousLogsPage = byId("previousLogsPage");
  const nextLogsPage = byId("nextLogsPage");

  const profileAvatar = byId("profileAvatar");
  const profileName = byId("profileName");
  const profileRole = byId("profileRole");

  const numberFormatter = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
  const dateTimeFormatter = new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const shortDateFormatter = new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "2-digit" });

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function valueAt(source, path) {
    return String(path).split(".").reduce((value, key) => {
      if (value === null || value === undefined || typeof value !== "object") return undefined;
      return value[key];
    }, source);
  }

  function firstValue(source, paths, fallback = undefined) {
    for (const path of paths) {
      const value = valueAt(source, path);
      if (value !== undefined && value !== null && value !== "") return value;
    }
    return fallback;
  }

  function numericValue(source, paths) {
    const value = firstValue(source, paths);
    if (value === undefined || value === null || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function asArray(value) {
    if (Array.isArray(value)) return value;
    if (!value || typeof value !== "object") return [];
    for (const key of ["items", "rows", "results", "data", "points"]) {
      if (Array.isArray(value[key])) return value[key];
    }
    return [];
  }

  function formatInteger(value) {
    const number = Number(value);
    return Number.isFinite(number) ? numberFormatter.format(number) : "—";
  }

  function percentNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    return Math.max(0, Math.min(100, number >= 0 && number <= 1 ? number * 100 : number));
  }

  function formatPercentageNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `%${numberFormatter.format(Math.max(0, Math.min(100, number)))}` : "—";
  }

  function formatDuration(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) return "—";
    const totalSeconds = Math.round(number);
    if (totalSeconds < 60) return `${totalSeconds} sn`;
    const totalMinutes = Math.floor(totalSeconds / 60);
    if (totalMinutes < 60) return `${totalMinutes} dk`;
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours < 24) return minutes ? `${hours} sa ${minutes} dk` : `${hours} sa`;
    const days = Math.floor(hours / 24);
    const remainderHours = hours % 24;
    return remainderHours ? `${days} gün ${remainderHours} sa` : `${days} gün`;
  }

  function parseDate(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatDateTime(value) {
    const date = parseDate(value);
    return date ? dateTimeFormatter.format(date) : "—";
  }

  function formatTrendDate(value) {
    const date = parseDate(value);
    return date ? shortDateFormatter.format(date) : String(value ?? "—");
  }

  function initials(value) {
    const words = String(value ?? "").trim().split(/\s+/).filter(Boolean);
    if (!words.length) return "—";
    return words.slice(0, 2).map(word => word[0]).join("").toLocaleUpperCase("tr-TR");
  }

  function statusClass(value) {
    const status = String(value ?? "").toLocaleLowerCase("tr-TR");
    if (["success", "successful", "succeeded", "completed", "ok", "başarılı", "tamamlandı"].some(item => status.includes(item))) return "success";
    if (["fail", "error", "partial", "başarısız", "hata", "kısmi"].some(item => status.includes(item))) return "failed";
    if (["run", "progress", "active", "çalış", "devam"].some(item => status.includes(item))) return "running";
    if (["pending", "queued", "bekle"].some(item => status.includes(item))) return "pending";
    if (["cancel", "iptal"].some(item => status.includes(item))) return "cancelled";
    return "neutral";
  }

  function statusLabel(value) {
    const normalized = statusClass(value);
    const labels = {
      success: "Başarılı",
      failed: "Başarısız",
      running: "Devam ediyor",
      pending: "Bekliyor",
      cancelled: "İptal edildi",
      neutral: String(value || "—"),
    };
    return labels[normalized];
  }

  function safeUrl(value) {
    if (!value) return null;
    try {
      const url = new URL(String(value), window.location.origin);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch (_error) {
      return null;
    }
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  function requestError(data, fallback) {
    return String(firstValue(data, ["detail", "message", "error"], fallback));
  }

  function setLoading(loading) {
    refreshButton.disabled = loading;
    refreshButton.classList.toggle("loading", loading);
    refreshState.classList.toggle("loading", loading);
    if (loading) {
      refreshState.classList.remove("error");
      refreshState.textContent = "Veriler yenileniyor";
    }
  }

  function setFilterOptions(select, items, placeholder, valuePaths, labelPaths) {
    const selected = select.value;
    const options = [];
    const seen = new Set();
    for (const item of asArray(items)) {
      const rawValue = typeof item === "object" ? firstValue(item, valuePaths) : item;
      const rawLabel = typeof item === "object" ? firstValue(item, labelPaths, rawValue) : item;
      if (rawValue === undefined || rawValue === null || rawValue === "") continue;
      const value = String(rawValue);
      if (seen.has(value)) continue;
      seen.add(value);
      options.push({ value, label: String(rawLabel || value) });
    }
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${options.map(option => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`).join("")}`;
    if (seen.has(selected)) select.value = selected;
  }

  function renderFilters(filters) {
    const source = filters && typeof filters === "object" ? filters : {};
    setFilterOptions(
      applicationFilter,
      firstValue(source, ["applications", "application_options", "available_applications"], []),
      "Tüm uygulamalar",
      ["value", "id", "key", "application"],
      ["label", "name", "display_name", "application"],
    );
    setFilterOptions(
      actorFilter,
      firstValue(source, ["actors", "users", "actor_options", "available_actors"], []),
      "Tüm kullanıcılar",
      ["value", "id", "key", "actor", "username"],
      ["label", "display_name", "name", "actor", "username"],
    );
    const rawStatuses = firstValue(source, ["statuses", "status_options", "available_statuses"], []);
    const localizedStatuses = asArray(rawStatuses).map(item => {
      if (item && typeof item === "object") return item;
      const value = String(item);
      const labels = {
        success: "Başarılı",
        failure: "Başarısız",
        partial: "Kısmi",
        cancelled: "İptal edildi",
        running: "Devam ediyor",
      };
      return { value, label: labels[value] || value };
    });
    setFilterOptions(
      statusFilter,
      localizedStatuses,
      "Tüm durumlar",
      ["value", "id", "key", "status"],
      ["label", "display_name", "name", "status"],
    );
  }

  function renderIdentity(identity) {
    state.identity = identity && typeof identity === "object" ? identity : {};
    const clientId = String(firstValue(state.identity, ["client_id"], ""));
    const displayName = clientId.startsWith("ip:")
      ? (clientId.slice(3) || "IP bilinmiyor")
      : "IP bilinmiyor";
    profileName.textContent = displayName;
    profileRole.textContent = "Bağlanan IP";
    profileAvatar.textContent = "IP";
  }

  function summaryValue(summary, paths) {
    return numericValue(summary, paths);
  }

  function renderSummary(summary) {
    const source = summary && typeof summary === "object" ? summary : {};
    const total = summaryValue(source, ["total_operations", "operation_count", "total_count", "operations.total", "total"]);
    const successful = summaryValue(source, ["successful_operations", "success_count", "succeeded_count", "operations.successful", "successful", "succeeded"]);
    const failed = summaryValue(source, ["failed_operations", "failure_count", "failed_count", "operations.failed", "failed"]);
    const running = summaryValue(source, ["running_operations", "running_count", "in_progress_count", "operations.running", "running"]);
    const activeUserCount = summaryValue(source, ["active_users", "active_user_count", "users.active"]);
    const userCount = summaryValue(source, ["total_users", "user_count", "known_users", "users.total"]);
    const activeSeconds = summaryValue(source, ["active_seconds", "active_usage_seconds", "total_active_seconds", "usage.active_seconds"]);
    const processSeconds = summaryValue(source, ["processing_seconds", "operation_seconds", "total_processing_seconds", "usage.processing_seconds"]);
    let successPercentage = percentNumber(firstValue(source, ["success_rate", "successful_rate", "rates.success"]));
    let failurePercentage = percentNumber(firstValue(source, ["failure_rate", "failed_rate", "rates.failure"]));

    const completed = successful !== null && failed !== null ? successful + failed : null;
    if (successPercentage === null && completed !== null && completed > 0) successPercentage = (successful / completed) * 100;
    if (failurePercentage === null && completed !== null && completed > 0) failurePercentage = (failed / completed) * 100;
    if (successful !== null && failed !== null && successful + failed === 0) {
      successPercentage = null;
      failurePercentage = null;
    }

    totalOperations.textContent = formatInteger(total);
    totalOperationsNote.textContent = firstValue(source, ["period_label"], daysFilter.selectedOptions[0]?.textContent || `Son ${daysFilter.value} gün`);
    successfulOperations.textContent = formatInteger(successful);
    successRate.textContent = `Başarı oranı ${successPercentage === null ? "—" : formatPercentageNumber(successPercentage)}`;
    failedOperations.textContent = formatInteger(failed);
    failureRate.textContent = `Hata oranı ${failurePercentage === null ? "—" : formatPercentageNumber(failurePercentage)}`;
    runningOperations.textContent = formatInteger(running);
    activeUsers.textContent = formatInteger(activeUserCount);
    knownUsers.textContent = userCount === null ? "Toplam kullanıcı —" : `Toplam ${formatInteger(userCount)} kullanıcı`;
    activeUsage.textContent = formatDuration(activeSeconds);
    processingTime.textContent = `İşlem süresi ${formatDuration(processSeconds)}`;

    const knownTotal = total !== null && total >= 0;
    const successCount = successful === null ? null : Math.max(0, successful);
    const failedCount = failed === null ? null : Math.max(0, failed);
    const otherCount = knownTotal && successCount !== null && failedCount !== null
      ? Math.max(0, total - successCount - failedCount)
      : null;

    resultSuccessCount.textContent = formatInteger(successCount);
    resultFailedCount.textContent = formatInteger(failedCount);
    resultOtherCount.textContent = formatInteger(otherCount);
    resultRingValue.textContent = successPercentage === null ? "—" : formatPercentageNumber(successPercentage);

    const hasDistribution = knownTotal && total > 0 && successCount !== null && failedCount !== null;
    resultRing.classList.toggle("empty", !hasDistribution);
    if (hasDistribution) {
      const successAngle = Math.max(0, Math.min(360, (successCount / total) * 360));
      const failedAngle = Math.max(successAngle, Math.min(360, ((successCount + failedCount) / total) * 360));
      resultRing.style.setProperty("--success-angle", `${successAngle}deg`);
      resultRing.style.setProperty("--failure-angle", `${failedAngle}deg`);
      resultRing.setAttribute("aria-label", `İşlem dağılımı: ${formatInteger(successCount)} başarılı, ${formatInteger(failedCount)} başarısız, ${formatInteger(otherCount)} diğer`);
    } else {
      resultRing.style.removeProperty("--success-angle");
      resultRing.style.removeProperty("--failure-angle");
      resultRing.setAttribute("aria-label", "Başarı oranı verisi yok");
    }
  }

  function normalizeTrend(rawTrend) {
    if (Array.isArray(rawTrend)) return rawTrend;
    if (!rawTrend || typeof rawTrend !== "object") return [];
    const items = asArray(rawTrend);
    if (items.length) return items;
    const labels = asArray(rawTrend.labels);
    if (!labels.length) return [];
    const totals = asArray(firstValue(rawTrend, ["totals", "values"], []));
    const successes = asArray(firstValue(rawTrend, ["successful", "successes"], []));
    const failures = asArray(firstValue(rawTrend, ["failed", "failures"], []));
    return labels.map((label, index) => ({
      label,
      total: totals[index],
      successful: successes[index],
      failed: failures[index],
    }));
  }

  function trendPoint(item, index) {
    const source = item && typeof item === "object" ? item : { total: item };
    const label = firstValue(source, ["date", "day", "label", "period"], index + 1);
    let total = numericValue(source, ["total_operations", "operation_count", "total", "count"]);
    const successful = numericValue(source, ["successful_operations", "success_count", "success", "successful", "succeeded"]);
    const failed = numericValue(source, ["failed_operations", "failure_count", "failed_count", "failed"]);
    let other = numericValue(source, ["other_operations", "other_count", "other"]);
    if (total === null && [successful, failed, other].some(value => value !== null)) total = (successful || 0) + (failed || 0) + (other || 0);
    if (total !== null && other === null) other = Math.max(0, total - (successful || 0) - (failed || 0));
    return {
      label,
      total: Math.max(0, total || 0),
      successful: Math.max(0, successful || 0),
      failed: Math.max(0, failed || 0),
      other: Math.max(0, other || 0),
      hasValue: total !== null,
    };
  }

  function renderTrend(rawTrend) {
    const points = normalizeTrend(rawTrend).map(trendPoint).filter(point => point.hasValue);
    if (!points.length || !points.some(point => point.total > 0)) {
      trendChart.innerHTML = '<p class="empty-state">Seçili filtrelerde işlem trendi bulunamadı.</p>';
      return;
    }
    const maximum = Math.max(...points.map(point => point.total), 0);
    const labelStep = Math.max(1, Math.ceil(points.length / 8));
    trendChart.innerHTML = `
      <div class="trend-columns">
        ${points.map((point, index) => {
          const height = maximum > 0 ? (point.total / maximum) * 100 : 0;
          const successfulHeight = point.total > 0 ? (point.successful / point.total) * 100 : 0;
          const failedHeight = point.total > 0 ? (point.failed / point.total) * 100 : 0;
          const otherHeight = point.total > 0 ? Math.max(0, 100 - successfulHeight - failedHeight) : 0;
          const showLabel = index === 0 || index === points.length - 1 || index % labelStep === 0;
          const title = `${formatTrendDate(point.label)} · ${formatInteger(point.total)} işlem · ${formatInteger(point.successful)} başarılı · ${formatInteger(point.failed)} başarısız`;
          return `
            <div class="trend-column" title="${escapeHtml(title)}">
              <div class="trend-bar-space">
                <div class="trend-bar" style="--bar-height:${height}%;--bar-min-height:${point.total > 0 ? 3 : 0}px">
                  <span class="trend-segment success" style="height:${successfulHeight}%"></span>
                  <span class="trend-segment failed" style="height:${failedHeight}%"></span>
                  <span class="trend-segment other" style="height:${otherHeight}%"></span>
                </div>
              </div>
              <span class="trend-label${showLabel ? "" : " hidden-label"}">${escapeHtml(formatTrendDate(point.label))}</span>
            </div>
          `;
        }).join("")}
      </div>
    `;
    trendChart.setAttribute("aria-label", `${points.length} zaman diliminde işlem trendi. En yüksek değer ${formatInteger(maximum)} işlem.`);
  }

  function renderUsers(rawUsers) {
    const users = asArray(rawUsers);
    usersMeta.textContent = users.length ? `${formatInteger(users.length)} istemci IP` : "İstemci IP yok";
    if (!users.length) {
      usersTableBody.innerHTML = '<tr><td colspan="7"><p class="empty-state table-empty">Seçili filtrelerde istemci aktivitesi bulunamadı.</p></td></tr>';
      return;
    }
    usersTableBody.innerHTML = users.map(user => {
      const name = firstValue(user, ["display_name", "name", "username", "actor"], "IP bilinmiyor");
      const activeSeconds = numericValue(user, ["active_seconds", "active_usage_seconds", "usage_seconds"]);
      const operations = numericValue(user, ["operation_count", "total_operations", "operations", "total"]);
      const successes = numericValue(user, ["success_count", "successful_operations", "successful"]);
      const failures = numericValue(user, ["failure_count", "failed_count", "failed_operations", "failed"]);
      const lastOperation = firstValue(user, ["last_operation", "last_operation_name", "last_action", "operation_type"], "—");
      const lastSeen = firstValue(user, ["last_seen_at", "last_seen", "last_active_at", "updated_at"]);
      return `
        <tr>
          <td>
            <div class="user-cell">
              <span class="user-avatar" aria-hidden="true">${escapeHtml(initials(name))}</span>
              <span class="user-copy"><strong>${escapeHtml(name)}</strong></span>
            </div>
          </td>
          <td>${escapeHtml(formatDuration(activeSeconds))}</td>
          <td><strong>${escapeHtml(formatInteger(operations))}</strong></td>
          <td class="metric-positive">${escapeHtml(formatInteger(successes))}</td>
          <td class="metric-negative">${escapeHtml(formatInteger(failures))}</td>
          <td>${escapeHtml(lastOperation)}</td>
          <td>${escapeHtml(formatDateTime(lastSeen))}</td>
        </tr>
      `;
    }).join("");
  }

  function applicationItems(rawApplications) {
    const source = asArray(rawApplications);
    const flattened = [];
    for (const item of source) {
      const children = asArray(firstValue(item, ["applications", "items", "children"], []));
      if (children.length) flattened.push(...children);
      else flattened.push(item);
    }
    return flattened;
  }

  function normalizeApplicationGroups(rawApplications) {
    const source = asArray(rawApplications);
    const groups = new Map();
    for (const item of source) {
      const children = asArray(firstValue(item, ["applications", "items", "children"], []));
      if (children.length) {
        const groupName = firstValue(item, ["group_name", "group", "category", "label", "name"], "Diğer uygulamalar");
        if (!groups.has(groupName)) groups.set(groupName, []);
        groups.get(groupName).push(...children);
        continue;
      }
      const groupName = firstValue(item, ["group_name", "group", "category"], "Diğer uygulamalar");
      if (!groups.has(groupName)) groups.set(groupName, []);
      groups.get(groupName).push(item);
    }
    return Array.from(groups, ([name, applications]) => ({ name, applications }));
  }

  function applicationName(item) {
    return firstValue(item, ["display_name", "label", "name", "application"], "Uygulama");
  }

  function applicationKey(item) {
    return String(firstValue(item, ["key", "id", "application", "name"], "")).toLocaleLowerCase("tr-TR");
  }

  function renderApplications(rawApplications) {
    const groups = normalizeApplicationGroups(rawApplications);
    const applicationCount = groups.reduce((total, group) => total + group.applications.length, 0);
    applicationsMeta.textContent = applicationCount ? `${formatInteger(applicationCount)} uygulama` : "Uygulama yok";
    if (!groups.length) {
      applicationGroups.innerHTML = '<p class="empty-state">Seçili filtrelerde uygulama kullanım verisi bulunamadı.</p>';
      return;
    }
    applicationGroups.innerHTML = groups.map(group => {
      const groupOperations = group.applications.reduce((total, application) => {
        const count = numericValue(application, ["operation_count", "total_operations", "operations", "total"]);
        return total + (count || 0);
      }, 0);
      return `
        <article class="application-group">
          <div class="application-group-head">
            <span>${escapeHtml(group.name)}</span>
            <strong>${escapeHtml(formatInteger(groupOperations))} işlem</strong>
          </div>
          <div class="application-list">
            ${group.applications.map(application => {
              const name = applicationName(application);
              const icon = firstValue(application, ["icon"], initials(name));
              const operationCount = numericValue(application, ["operation_count", "total_operations", "operations", "total"]);
              let rate = percentNumber(firstValue(application, ["success_rate", "successful_rate"]));
              const successCount = numericValue(application, ["success_count", "successful_operations", "successful"]);
              if (rate === null && operationCount !== null && operationCount > 0 && successCount !== null) rate = (successCount / operationCount) * 100;
              const activeSeconds = numericValue(application, ["active_seconds", "active_usage_seconds", "usage_seconds"]);
              const availability = String(firstValue(application, ["status", "availability"], "")).toLocaleLowerCase("tr-TR");
              const availabilityLabel = availability === "online" ? "Çevrimiçi" : (availability === "offline" ? "Çevrimdışı" : "");
              let metricDetail = operationCount === 0
                ? "Henüz işlem yok"
                : (rate !== null ? `${formatPercentageNumber(rate)} başarı` : (activeSeconds !== null ? `${formatDuration(activeSeconds)} kullanım` : "Kullanım ayrıntısı yok"));
              const detail = [availabilityLabel, metricDetail].filter(Boolean).join(" · ");
              const url = safeUrl(firstValue(application, ["url", "href", "application_url"]));
              const tag = url ? "a" : "div";
              const linkAttributes = url ? ` href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"` : "";
              return `
                <${tag} class="application-item"${linkAttributes}>
                  <span class="application-icon" aria-hidden="true">${escapeHtml(icon)}</span>
                  <span class="application-copy"><strong>${escapeHtml(name)}</strong><small>${escapeHtml(detail)}</small></span>
                  <span class="application-count"><strong>${escapeHtml(formatInteger(operationCount))}</strong><small>işlem</small></span>
                </${tag}>
              `;
            }).join("")}
          </div>
        </article>
      `;
    }).join("");
  }

  function renderRunningJobs(rawJobs) {
    const jobs = asArray(rawJobs);
    if (!jobs.length) {
      runningJobsList.innerHTML = '<p class="empty-state">Şu anda devam eden işlem yok.</p>';
      return;
    }
    runningJobsList.innerHTML = jobs.map(job => {
      const operation = firstValue(job, ["operation_name", "operation", "name", "title", "event_type"], "İşlem");
      const application = firstValue(job, ["application_name", "application", "app"], "Uygulama");
      const actor = firstValue(job, ["display_name", "actor_name", "actor", "username"], "IP bilinmiyor");
      const startedAt = firstValue(job, ["started_at", "start_time", "created_at"]);
      let elapsedSeconds = numericValue(job, ["elapsed_seconds", "duration_seconds"]);
      const startDate = parseDate(startedAt);
      if (elapsedSeconds === null && startDate) elapsedSeconds = Math.max(0, (Date.now() - startDate.getTime()) / 1000);
      let progress = numericValue(job, ["progress_percent", "progress", "completion"]);
      if (progress !== null && progress >= 0 && progress <= 1) progress *= 100;
      if (progress !== null) progress = Math.max(0, Math.min(100, progress));
      const progressLabel = progress === null ? "İlerleme bilgisi yok" : `%${numberFormatter.format(progress)} tamamlandı`;
      return `
        <article class="running-job">
          <div class="running-job-copy">
            <strong>${escapeHtml(operation)}</strong>
            <span>${escapeHtml(application)} · ${escapeHtml(actor)}${startedAt ? ` · ${escapeHtml(formatDateTime(startedAt))}` : ""}</span>
          </div>
          <span class="running-job-time">${escapeHtml(formatDuration(elapsedSeconds))}</span>
          <div class="job-progress${progress === null ? " indeterminate" : ""}" title="${escapeHtml(progressLabel)}" aria-label="${escapeHtml(progressLabel)}"><span${progress === null ? "" : ` style="--progress:${progress}%"`}></span></div>
        </article>
      `;
    }).join("");
  }

  function notificationClass(value) {
    const severity = String(value ?? "").toLocaleLowerCase("tr-TR");
    if (["error", "critical", "danger", "hata", "kritik"].some(item => severity.includes(item))) return "error";
    if (["warn", "uyarı"].some(item => severity.includes(item))) return "warning";
    if (["success", "başar"].some(item => severity.includes(item))) return "success";
    return "info";
  }

  function renderNotifications(rawNotifications) {
    const notifications = asArray(rawNotifications);
    notificationsMeta.textContent = notifications.length ? `${formatInteger(notifications.length)} bildirim` : "Bildirim yok";
    if (!notifications.length) {
      notificationsList.innerHTML = '<p class="empty-state">Dikkat gerektiren bildirim yok.</p>';
      return;
    }
    notificationsList.innerHTML = notifications.map(notification => {
      const title = firstValue(notification, ["title", "name", "event"], "Bildirim");
      const message = firstValue(notification, ["message", "description", "detail"], "");
      const application = firstValue(notification, ["application_name", "application", "app"]);
      const timestamp = firstValue(notification, ["created_at", "timestamp", "occurred_at", "time"]);
      const meta = [application, timestamp ? formatDateTime(timestamp) : null].filter(Boolean).join(" · ");
      const severity = notificationClass(firstValue(notification, ["severity", "level", "status"]));
      return `
        <article class="notification-item ${severity}">
          <span class="notification-marker" aria-hidden="true"></span>
          <div class="notification-copy">
            <strong>${escapeHtml(title)}</strong>
            ${message ? `<p>${escapeHtml(message)}</p>` : ""}
            ${meta ? `<small>${escapeHtml(meta)}</small>` : ""}
          </div>
        </article>
      `;
    }).join("");
  }

  function normalizeLogType(log) {
    const type = String(firstValue(log, ["kind", "log_type", "type", "category", "source"], "user")).toLocaleLowerCase("tr-TR");
    if (["technical", "system", "service", "backend", "error", "teknik"].some(item => type.includes(item))) return "technical";
    return "user";
  }

  function filteredLogs() {
    const query = state.logSearch.trim().toLocaleLowerCase("tr-TR");
    return state.logs.filter(log => {
      if (state.logType !== "all" && normalizeLogType(log) !== state.logType) return false;
      if (!query) return true;
      const searchable = [
        firstValue(log, ["display_name", "actor_name", "actor", "username"]),
        firstValue(log, ["application_name", "application", "app"]),
        firstValue(log, ["operation_name", "operation", "event", "event_type"]),
        firstValue(log, ["status", "result"]),
        firstValue(log, ["message", "description", "detail"]),
      ].filter(Boolean).join(" ").toLocaleLowerCase("tr-TR");
      return searchable.includes(query);
    });
  }

  function renderLogs() {
    const logs = filteredLogs();
    const pageCount = Math.max(1, Math.ceil(logs.length / LOG_PAGE_SIZE));
    state.logPage = Math.min(Math.max(1, state.logPage), pageCount);
    const start = (state.logPage - 1) * LOG_PAGE_SIZE;
    const pageItems = logs.slice(start, start + LOG_PAGE_SIZE);

    if (!pageItems.length) {
      const message = state.logs.length ? "Arama ve tür seçimiyle eşleşen kayıt yok." : "Seçili filtrelerde aktivite kaydı bulunamadı.";
      logsTableBody.innerHTML = `<tr><td colspan="7"><p class="empty-state table-empty">${escapeHtml(message)}</p></td></tr>`;
    } else {
      logsTableBody.innerHTML = pageItems.map(log => {
        const timestamp = firstValue(log, ["created_at", "timestamp", "occurred_at", "time"]);
        const type = normalizeLogType(log);
        const actor = firstValue(log, ["display_name", "actor_name", "actor", "username"], "—");
        const application = firstValue(log, ["application_name", "application", "app"], "—");
        const operation = firstValue(log, ["operation_name", "operation", "event", "event_type"], "—");
        const rawStatus = firstValue(log, ["status", "result"], "—");
        const message = firstValue(log, ["message", "description", "detail"], [firstValue(log, ["method"]), firstValue(log, ["path"])].filter(Boolean).join(" ") || "—");
        return `
          <tr>
            <td>${escapeHtml(formatDateTime(timestamp))}</td>
            <td><span class="log-type-pill ${type}">${type === "technical" ? "Teknik" : "İstemci"}</span></td>
            <td>${escapeHtml(actor)}</td>
            <td>${escapeHtml(application)}</td>
            <td>${escapeHtml(operation)}</td>
            <td><span class="status-pill ${statusClass(rawStatus)}">${escapeHtml(statusLabel(rawStatus))}</span></td>
            <td><span class="log-message" title="${escapeHtml(message)}">${escapeHtml(message)}</span></td>
          </tr>
        `;
      }).join("");
    }

    logsMeta.textContent = logs.length ? `${formatInteger(logs.length)} kayıt · ${formatInteger(start + 1)}–${formatInteger(Math.min(start + LOG_PAGE_SIZE, logs.length))} gösteriliyor` : "Kayıt yok";
    logsPage.textContent = logs.length ? `${state.logPage} / ${pageCount}` : "—";
    previousLogsPage.disabled = state.logPage <= 1 || !logs.length;
    nextLogsPage.disabled = state.logPage >= pageCount || !logs.length;
  }

  function renderDashboard(data) {
    const dashboard = data && typeof data === "object" ? data : {};
    state.dashboard = dashboard;
    renderIdentity(dashboard.identity);
    renderSummary(dashboard.summary);
    renderTrend(dashboard.trend);
    renderUsers(dashboard.users);
    renderApplications(dashboard.applications);
    renderRunningJobs(dashboard.running_jobs);
    renderNotifications(dashboard.notifications);
    state.logs = asArray(dashboard.logs);
    state.logPage = 1;
    renderLogs();
    renderFilters(dashboard.filters);
  }

  function showInitialError(message) {
    const escaped = escapeHtml(message);
    trendChart.innerHTML = `<p class="empty-state error">${escaped}</p>`;
    usersTableBody.innerHTML = `<tr><td colspan="7"><p class="empty-state table-empty error">${escaped}</p></td></tr>`;
    applicationGroups.innerHTML = `<p class="empty-state error">${escaped}</p>`;
    runningJobsList.innerHTML = `<p class="empty-state error">${escaped}</p>`;
    notificationsList.innerHTML = `<p class="empty-state error">${escaped}</p>`;
    logsTableBody.innerHTML = `<tr><td colspan="7"><p class="empty-state table-empty error">${escaped}</p></td></tr>`;
  }

  function dashboardQuery() {
    return new URLSearchParams({
      days: daysFilter.value || "30",
      application: applicationFilter.value,
      actor: actorFilter.value,
      status: statusFilter.value,
    });
  }

  async function loadDashboard({ quiet = false } = {}) {
    if (state.requestController) state.requestController.abort();
    const controller = new AbortController();
    state.requestController = controller;
    if (!quiet) setLoading(true);
    else refreshState.textContent = "Arka planda yenileniyor";

    try {
      const response = await fetch(`/analytics/dashboard?${dashboardQuery().toString()}`, {
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Dashboard verileri alınamadı."));
      renderDashboard(data);
      state.lastLoadedAt = Date.now();
      const refreshedAt = new Date(state.lastLoadedAt);
      refreshState.classList.remove("error");
      refreshState.textContent = `${refreshedAt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })} güncellendi · 30 sn'de bir yenilenir`;
      dataTimestamp.textContent = `Son güncelleme: ${dateTimeFormatter.format(refreshedAt)}`;
    } catch (error) {
      if (error?.name === "AbortError") return;
      const message = error instanceof Error ? error.message : "Dashboard verileri alınamadı.";
      refreshState.classList.add("error");
      refreshState.textContent = message;
      if (!state.dashboard) showInitialError(message);
    } finally {
      if (state.requestController === controller) {
        state.requestController = null;
        setLoading(false);
      }
    }
  }

  function createSessionId() {
    try {
      const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (stored) return stored;
      const suffix = typeof crypto?.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      const sessionId = `smartaios-${suffix}`;
      sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
      return sessionId;
    } catch (_error) {
      return `smartaios-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    }
  }

  const analyticsSessionId = createSessionId();
  let accumulatedActiveSeconds = 0;
  let activeClockStartedAt = performance.now();
  let pageWasActive = document.visibilityState === "visible" && document.hasFocus();

  function captureActiveSeconds() {
    const now = performance.now();
    if (pageWasActive) accumulatedActiveSeconds += Math.max(0, (now - activeClockStartedAt) / 1000);
    activeClockStartedAt = now;
    pageWasActive = document.visibilityState === "visible" && document.hasFocus();
  }

  function heartbeatPayload(seconds) {
    return {
      session_id: analyticsSessionId,
      application: "big_agent",
      current_view: "dashboard",
      active_seconds_delta: seconds,
    };
  }

  async function sendHeartbeat() {
    captureActiveSeconds();
    const seconds = Math.min(60, Math.floor(accumulatedActiveSeconds));
    if (seconds <= 0) return;
    accumulatedActiveSeconds -= seconds;
    try {
      const response = await fetch("/analytics/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(heartbeatPayload(seconds)),
        keepalive: true,
      });
      if (!response.ok) accumulatedActiveSeconds += seconds;
    } catch (_error) {
      accumulatedActiveSeconds += seconds;
    }
  }

  function flushHeartbeat() {
    captureActiveSeconds();
    const seconds = Math.min(60, Math.floor(accumulatedActiveSeconds));
    if (seconds <= 0 || typeof navigator.sendBeacon !== "function") return;
    accumulatedActiveSeconds -= seconds;
    const body = new Blob([JSON.stringify(heartbeatPayload(seconds))], { type: "application/json" });
    if (!navigator.sendBeacon("/analytics/heartbeat", body)) accumulatedActiveSeconds += seconds;
  }

  dashboardFilters.addEventListener("change", () => loadDashboard());
  refreshButton.addEventListener("click", () => loadDashboard());

  logTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      state.logType = tab.dataset.logType || "all";
      state.logPage = 1;
      logTabs.forEach(item => {
        const active = item === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", String(active));
      });
      renderLogs();
    });
  });

  logSearch.addEventListener("input", () => {
    state.logSearch = logSearch.value;
    state.logPage = 1;
    renderLogs();
  });

  previousLogsPage.addEventListener("click", () => {
    state.logPage -= 1;
    renderLogs();
  });

  nextLogsPage.addEventListener("click", () => {
    state.logPage += 1;
    renderLogs();
  });

  document.querySelectorAll(".rail-navigation .rail-link").forEach(link => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".rail-navigation .rail-link").forEach(item => item.classList.toggle("active", item === link));
    });
  });

  ["visibilitychange", "focus", "blur"].forEach(eventName => {
    const target = eventName === "visibilitychange" ? document : window;
    target.addEventListener(eventName, captureActiveSeconds);
  });
  window.addEventListener("pagehide", flushHeartbeat);
  window.setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
  window.setInterval(() => {
    if (document.visibilityState === "visible" && !state.requestController) loadDashboard({ quiet: true });
  }, REFRESH_INTERVAL_MS);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && Date.now() - state.lastLoadedAt >= REFRESH_INTERVAL_MS) loadDashboard({ quiet: true });
  });

  loadDashboard();
})();
