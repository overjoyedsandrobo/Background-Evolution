import pygame


def get_start_button_rect(canvas_w, canvas_h):
    btn_w = int(canvas_w * 0.62)
    btn_h = int(canvas_h * 0.11)
    return pygame.Rect((canvas_w - btn_w) // 2, int(canvas_h * 0.74), btn_w, btn_h)


def get_save_slot_rect(canvas_w, canvas_h, num_save_slots, slot_index):
    slot_h = canvas_h // num_save_slots
    top = slot_index * slot_h
    bottom = canvas_h if slot_index == num_save_slots - 1 else (slot_index + 1) * slot_h
    return pygame.Rect(0, top, canvas_w, bottom - top)


def get_ui_layout(canvas_w, canvas_h, egg_rect, canvas_scale):
    padding = 0
    panel_gap = int(18 * canvas_scale)
    tab_height = int(34 * canvas_scale)
    bottom_margin = 0

    panel_top = egg_rect.bottom + panel_gap
    max_panel_top = canvas_h - bottom_margin - tab_height - int(120 * canvas_scale)
    panel_top = min(panel_top, max_panel_top)

    tabs_rect = pygame.Rect(padding, panel_top, max(1, canvas_w - padding * 2), tab_height)
    page_rect = pygame.Rect(
        padding,
        tabs_rect.bottom,
        max(1, canvas_w - padding * 2),
        max(1, canvas_h - tabs_rect.bottom - bottom_margin),
    )
    tab_w = tabs_rect.width // 2
    stats_tab_rect = pygame.Rect(tabs_rect.x, tabs_rect.y, tab_w, tabs_rect.height)
    path_tab_rect = pygame.Rect(tabs_rect.x + tab_w, tabs_rect.y, tabs_rect.width - tab_w, tabs_rect.height)
    return stats_tab_rect, path_tab_rect, page_rect


def get_stats_row_rect_for_label(canvas_w, canvas_h, egg_rect, canvas_scale, stat_items, target_label):
    _, _, page_rect = get_ui_layout(canvas_w, canvas_h, egg_rect, canvas_scale)
    if not stat_items:
        return None
    row_h = max(1, page_rect.height // len(stat_items))
    for i, label in enumerate(stat_items):
        if label == target_label:
            return pygame.Rect(page_rect.x, page_rect.y + i * row_h, page_rect.width, row_h)
    return None


def draw_lock_on_card(canvas, lock_image, card_rect):
    if lock_image is None:
        return
    max_w = max(8, int(card_rect.width * 0.38))
    max_h = max(8, int(card_rect.height * 0.38))
    img_w, img_h = lock_image.get_size()
    fit = min(max_w / img_w, max_h / img_h)
    draw_w = max(1, int(img_w * fit))
    draw_h = max(1, int(img_h * fit))
    lock_scaled = pygame.transform.smoothscale(lock_image, (draw_w, draw_h))
    lock_rect = lock_scaled.get_rect(center=(card_rect.centerx, card_rect.centery))
    canvas.blit(lock_scaled, lock_rect)


def draw_start_menu(canvas, canvas_w, canvas_h, font, start_bg_image):
    if start_bg_image is not None:
        bg_scaled = pygame.transform.smoothscale(start_bg_image, (canvas_w, canvas_h))
        canvas.blit(bg_scaled, (0, 0))
    else:
        canvas.fill((22, 30, 44))

    title_surf = font.render("Background Evolution", True, (240, 240, 245))
    canvas.blit(title_surf, title_surf.get_rect(center=(canvas_w // 2, int(canvas_h * 0.18))))

    start_btn = get_start_button_rect(canvas_w, canvas_h)
    pygame.draw.rect(canvas, (28, 125, 92), start_btn, border_radius=14)
    pygame.draw.rect(canvas, (200, 240, 226), start_btn, 2, border_radius=14)
    start_txt = font.render("Start Game", True, (245, 255, 248))
    canvas.blit(start_txt, start_txt.get_rect(center=start_btn.center))


def draw_save_select(canvas, canvas_w, canvas_h, font, save_slots, num_save_slots, canvas_scale, format_time):
    for idx in range(num_save_slots):
        slot_rect = get_save_slot_rect(canvas_w, canvas_h, num_save_slots, idx)
        shade = 42 + (idx % 2) * 8
        pygame.draw.rect(canvas, (shade, shade + 6, shade + 10), slot_rect)
        pygame.draw.rect(canvas, (85, 95, 110), slot_rect, 2)

        slot = save_slots[idx]
        slot_title = font.render(f"Save Slot {idx + 1}", True, (238, 238, 240))
        canvas.blit(slot_title, slot_title.get_rect(midleft=(int(20 * canvas_scale), slot_rect.top + int(26 * canvas_scale))))

        status_label = "Continue" if slot.get("used", False) else "New Game"
        action_color = (180, 225, 190) if slot.get("used", False) else (220, 220, 230)
        action_surf = font.render(status_label, True, action_color)
        canvas.blit(action_surf, action_surf.get_rect(midleft=(int(20 * canvas_scale), slot_rect.top + int(58 * canvas_scale))))

        if slot.get("used", False):
            details = f"Time {format_time(slot.get('time_alive_seconds', 0.0))}"
            detail_surf = font.render(details, True, (195, 204, 215))
            canvas.blit(detail_surf, detail_surf.get_rect(midleft=(int(20 * canvas_scale), slot_rect.top + int(90 * canvas_scale))))


def draw_game_screen(
    canvas,
    canvas_w,
    canvas_h,
    font,
    canvas_scale,
    status_text,
    egg_sprite,
    egg_rect_draw,
    current_tab,
    stat_items,
    path_items,
    time_alive_seconds,
    format_time,
    lock_image,
):
    status_surf = font.render(status_text, True, (220, 220, 220))
    status_rect = status_surf.get_rect(center=(canvas_w // 2, int(36 * canvas_scale)))
    canvas.blit(status_surf, status_rect)
    canvas.blit(egg_sprite, egg_rect_draw)

    stats_tab_rect, path_tab_rect, page_rect = get_ui_layout(canvas_w, canvas_h, egg_rect_draw, canvas_scale)
    active_tab_color = (78, 98, 126)
    inactive_tab_color = (48, 48, 54)
    border_color = (90, 90, 96)
    text_color = (230, 230, 230)

    pygame.draw.rect(canvas, active_tab_color if current_tab == "stats" else inactive_tab_color, stats_tab_rect, border_radius=8)
    pygame.draw.rect(canvas, active_tab_color if current_tab == "path" else inactive_tab_color, path_tab_rect, border_radius=8)
    pygame.draw.rect(canvas, border_color, stats_tab_rect, 2, border_radius=8)
    pygame.draw.rect(canvas, border_color, path_tab_rect, 2, border_radius=8)

    stats_tab_text = font.render("Stats", True, text_color)
    path_tab_text = font.render("Path", True, text_color)
    canvas.blit(stats_tab_text, stats_tab_text.get_rect(center=stats_tab_rect.center))
    canvas.blit(path_tab_text, path_tab_text.get_rect(center=path_tab_rect.center))

    pygame.draw.rect(canvas, (40, 40, 44), page_rect, border_radius=10)
    pygame.draw.rect(canvas, border_color, page_rect, 2, border_radius=10)

    stat_values = {
        "Time Alive": format_time(time_alive_seconds),
        "Features": "0",
        "Power": "0",
        "Survivability": "0",
        "Adaptivness": "0",
        "Extra Stats": "",
    }

    if current_tab == "stats":
        row_h = max(1, page_rect.height // len(stat_items))
        for i, label in enumerate(stat_items):
            row = pygame.Rect(page_rect.x, page_rect.y + i * row_h, page_rect.width, row_h)
            if i % 2 == 1:
                pygame.draw.rect(canvas, (46, 46, 50), row)
            line_y = row.bottom - 1
            pygame.draw.line(canvas, (70, 70, 74), (row.x + 6, line_y), (row.right - 6, line_y), 1)

            label_color = (180, 220, 255) if label == "Extra Stats" else (210, 210, 210)
            value_color = (150, 220, 255) if label == "Extra Stats" else (190, 220, 190)
            label_surf = font.render(label, True, label_color)
            value_surf = font.render(stat_values.get(label, "0"), True, value_color)
            canvas.blit(label_surf, label_surf.get_rect(midleft=(row.x + int(12 * canvas_scale), row.centery)))
            canvas.blit(value_surf, value_surf.get_rect(midright=(row.right - int(12 * canvas_scale), row.centery)))
    else:
        card_w = page_rect.width // 2
        card_h = page_rect.height // 2
        for idx, label in enumerate(path_items):
            col = idx % 2
            row = idx // 2
            card = pygame.Rect(
                page_rect.x + col * card_w,
                page_rect.y + row * card_h,
                card_w if col == 0 else page_rect.width - card_w,
                card_h if row == 0 else page_rect.height - card_h,
            )
            pygame.draw.rect(canvas, (95, 95, 95), card)
            draw_lock_on_card(canvas, lock_image, card)
            label_surf = font.render(label, True, (240, 240, 240))
            canvas.blit(label_surf, label_surf.get_rect(midtop=(card.centerx, card.top + int(10 * canvas_scale))))
            locked_surf = font.render("Locked", True, (70, 70, 70))
            canvas.blit(locked_surf, locked_surf.get_rect(midbottom=(card.centerx, card.bottom - int(10 * canvas_scale))))

        divider_x = page_rect.x + card_w
        divider_y = page_rect.y + card_h
        pygame.draw.line(canvas, (0, 0, 0), (divider_x, page_rect.y), (divider_x, page_rect.bottom), 2)
        pygame.draw.line(canvas, (0, 0, 0), (page_rect.x, divider_y), (page_rect.right, divider_y), 2)

    return stats_tab_rect, path_tab_rect


def draw_extra_stats_page(canvas, canvas_w, canvas_h, font, canvas_scale, extra_stats):
    canvas.fill((26, 30, 36))
    title = font.render("Extra Stats", True, (236, 242, 248))
    canvas.blit(title, title.get_rect(midtop=(canvas_w // 2, int(16 * canvas_scale))))

    panel_top = int(56 * canvas_scale)
    panel = pygame.Rect(0, panel_top, canvas_w, max(1, canvas_h - panel_top))
    pygame.draw.rect(canvas, (40, 45, 52), panel)
    pygame.draw.line(canvas, (86, 96, 108), (panel.x, panel.y), (panel.right, panel.y), 2)

    all_items = list(extra_stats)
    if not all_items:
        return

    row_h = max(1, panel.height // len(all_items))
    for i, label in enumerate(all_items):
        row = pygame.Rect(panel.x, panel.y + i * row_h, panel.width, row_h)
        if i % 2 == 1:
            pygame.draw.rect(canvas, (46, 52, 60), row)
        label_text = font.render(label, True, (213, 225, 238))
        value_text = font.render("0", True, (190, 220, 190))
        canvas.blit(label_text, label_text.get_rect(midleft=(row.x + int(12 * canvas_scale), row.centery)))
        canvas.blit(value_text, value_text.get_rect(midright=(row.right - int(12 * canvas_scale), row.centery)))
