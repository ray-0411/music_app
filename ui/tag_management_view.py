import customtkinter as ctk

from config import APP_FONT_FAMILY
from database.tag_repository import TagRepository
from models.tag import TagCategory
from ui.fonts import base_font, button_font, small_title_font


class TagManagementView(ctk.CTkFrame):
    def __init__(self, master, *, tag_repository: TagRepository) -> None:
        super().__init__(master, fg_color="transparent")
        self.tag_repository = tag_repository
        self.categories: list[TagCategory] = []
        self.selected_category_id: int | None = None
        self.font = base_font()
        self.title_font = small_title_font()
        self.button_font = button_font()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_page = ctk.CTkFrame(self, fg_color="transparent")
        self.main_page.grid(row=0, column=0, sticky="nsew")
        self.main_page.grid_columnconfigure(0, weight=1)
        self.main_page.grid_rowconfigure(1, weight=1)

        self.recovery_page = ctk.CTkFrame(self, fg_color="transparent")
        self.recovery_page.grid(row=0, column=0, sticky="nsew")
        self.recovery_page.grid_columnconfigure(0, weight=1)
        self.recovery_page.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(self.main_page)
        form.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="新增上層", font=self.font).grid(
            row=0, column=0, sticky="w", padx=(12, 6), pady=12
        )
        self.category_entry = ctk.CTkEntry(form, font=self.font)
        self.category_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=12)
        ctk.CTkButton(
            form,
            text="新增",
            command=self.add_category,
            font=self.button_font,
            width=84,
        ).grid(row=0, column=2, padx=6, pady=12)
        ctk.CTkButton(
            form,
            text="恢復/刪除標籤",
            command=self.show_recovery_page,
            font=self.button_font,
        ).grid(row=0, column=3, sticky="w", padx=(6, 12), pady=12)

        body = ctk.CTkFrame(self.main_page, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.category_list = ctk.CTkScrollableFrame(body)
        self.category_list.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.category_list.grid_columnconfigure(0, weight=1)

        self.option_list = ctk.CTkScrollableFrame(body)
        self.option_list.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.option_list.grid_columnconfigure(0, weight=1)

        recovery_header = ctk.CTkFrame(self.recovery_page)
        recovery_header.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        recovery_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            recovery_header,
            text="恢復/刪除標籤",
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        ctk.CTkButton(
            recovery_header,
            text="返回",
            command=self.show_main_page,
            font=self.button_font,
        ).grid(row=0, column=1, sticky="e", padx=12, pady=12)

        disabled_body = ctk.CTkFrame(self.recovery_page, fg_color="transparent")
        disabled_body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        disabled_body.grid_columnconfigure(0, weight=1)
        disabled_body.grid_columnconfigure(1, weight=1)
        disabled_body.grid_rowconfigure(0, weight=1)

        self.disabled_category_list = ctk.CTkScrollableFrame(disabled_body)
        self.disabled_category_list.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.disabled_category_list.grid_columnconfigure(0, weight=1)

        self.disabled_option_list = ctk.CTkScrollableFrame(disabled_body)
        self.disabled_option_list.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.disabled_option_list.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(self, text="", anchor="w", font=self.font)
        self.status_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.status_label.grid_remove()

        self.reload()
        self.show_main_page()

    def reload(self) -> None:
        self.categories = self.tag_repository.list_categories()
        if self.selected_category_id is None and self.categories:
            self.selected_category_id = self.categories[0].id
        if self.selected_category_id not in {category.id for category in self.categories}:
            self.selected_category_id = self.categories[0].id if self.categories else None
        self.render_categories()
        self.render_options()
        if self.recovery_page.winfo_ismapped():
            self.render_disabled()

    def render_categories(self) -> None:
        for child in self.category_list.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.category_list,
            text="上層標籤",
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        if not self.categories:
            ctk.CTkLabel(self.category_list, text="尚無上層標籤", font=self.font).grid(
                row=1, column=0, sticky="ew", padx=8, pady=8
            )
            return
        for row, category in enumerate(self.categories, start=1):
            item = ctk.CTkFrame(self.category_list)
            item.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            item.grid_columnconfigure(0, weight=1)
            fg = ("gray80", "gray30") if category.id == self.selected_category_id else "transparent"
            item.configure(fg_color=fg)
            selected = ctk.BooleanVar(value=category.id == self.selected_category_id)
            ctk.CTkCheckBox(
                item,
                text=category.name,
                variable=selected,
                onvalue=True,
                offvalue=False,
                font=self.font,
                command=lambda category_id=category.id: self.select_category(category_id),
            ).grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            ctk.CTkButton(
                item,
                text="▲",
                width=72,
                font=self.button_font,
                command=lambda category_id=category.id: self.move_category(category_id, -1),
            ).grid(row=0, column=1, padx=4, pady=6)
            ctk.CTkButton(
                item,
                text="▼",
                width=72,
                font=self.button_font,
                command=lambda category_id=category.id: self.move_category(category_id, 1),
            ).grid(row=0, column=2, padx=4, pady=6)
            ctk.CTkButton(
                item,
                text="停用",
                width=72,
                font=self.button_font,
                command=lambda category_id=category.id: self.disable_category(category_id),
            ).grid(row=0, column=3, padx=(4, 8), pady=6)

    def render_options(self) -> None:
        for child in self.option_list.winfo_children():
            child.destroy()
        category = self.current_category()
        title = f"{category.name} 的下層標籤" if category else "下層標籤"
        ctk.CTkLabel(
            self.option_list,
            text=title,
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        if category is None:
            ctk.CTkLabel(self.option_list, text="請先新增上層標籤", font=self.font).grid(
                row=1, column=0, sticky="ew", padx=8, pady=8
            )
            return
        add_frame = ctk.CTkFrame(self.option_list)
        add_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 10))
        add_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(add_frame, text="新增下層", font=self.font).grid(
            row=0, column=0, sticky="w", padx=(10, 6), pady=10
        )
        self.option_entry = ctk.CTkEntry(add_frame, font=self.font)
        self.option_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        ctk.CTkButton(
            add_frame,
            text="新增",
            command=self.add_option,
            font=self.button_font,
            width=84,
        ).grid(row=0, column=2, padx=(6, 10), pady=10)
        options = self.tag_repository.list_options_by_category(category.id)
        if not options:
            ctk.CTkLabel(self.option_list, text="尚無下層標籤", font=self.font).grid(
                row=2, column=0, sticky="ew", padx=8, pady=8
            )
        for row, option in enumerate(options, start=2):
            item = ctk.CTkFrame(self.option_list)
            item.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            item.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(item, text=option.name, anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            ctk.CTkButton(
                item,
                text="▲",
                width=72,
                font=self.button_font,
                command=lambda option_id=option.id: self.move_option(option_id, -1),
            ).grid(row=0, column=1, padx=4, pady=6)
            ctk.CTkButton(
                item,
                text="▼",
                width=72,
                font=self.button_font,
                command=lambda option_id=option.id: self.move_option(option_id, 1),
            ).grid(row=0, column=2, padx=4, pady=6)
            ctk.CTkButton(
                item,
                text="停用",
                width=72,
                font=self.button_font,
                command=lambda option_id=option.id: self.disable_option(option_id),
            ).grid(row=0, column=3, padx=(4, 8), pady=6)

    def render_disabled(self) -> None:
        for child in self.disabled_category_list.winfo_children():
            child.destroy()
        for child in self.disabled_option_list.winfo_children():
            child.destroy()

        ctk.CTkLabel(
            self.disabled_category_list,
            text="已停用上層",
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        disabled_categories = self.tag_repository.list_unavailable_categories()
        if not disabled_categories:
            ctk.CTkLabel(self.disabled_category_list, text="沒有停用的上層標籤", font=self.font).grid(
                row=1, column=0, sticky="ew", padx=8, pady=8
            )
        for row, category in enumerate(disabled_categories, start=1):
            item = ctk.CTkFrame(self.disabled_category_list)
            item.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            item.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(item, text=category.name, anchor="w", font=self.font).grid(
                row=0, column=0, sticky="ew", padx=8, pady=8
            )
            ctk.CTkButton(
                item,
                text="恢復",
                width=72,
                font=self.button_font,
                command=lambda category_id=category.id: self.restore_category(category_id),
            ).grid(row=0, column=1, padx=4, pady=6)
            ctk.CTkButton(
                item,
                text="刪除",
                width=72,
                font=self.button_font,
                command=lambda category_id=category.id: self.delete_category(category_id),
            ).grid(row=0, column=2, padx=(4, 8), pady=6)

        ctk.CTkLabel(
            self.disabled_option_list,
            text="已停用下層",
            anchor="w",
            font=self.title_font,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        disabled_options = self.tag_repository.list_unavailable_options()
        if not disabled_options:
            ctk.CTkLabel(self.disabled_option_list, text="沒有停用的下層標籤", font=self.font).grid(
                row=1, column=0, sticky="ew", padx=8, pady=8
            )
        for row, (option, category_name) in enumerate(disabled_options, start=1):
            item = ctk.CTkFrame(self.disabled_option_list)
            item.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            item.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                item,
                text=f"{category_name} / {option.name}",
                anchor="w",
                font=self.font,
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            ctk.CTkButton(
                item,
                text="恢復",
                width=72,
                font=self.button_font,
                command=lambda option_id=option.id: self.restore_option(option_id),
            ).grid(row=0, column=1, padx=4, pady=6)
            ctk.CTkButton(
                item,
                text="刪除",
                width=72,
                font=self.button_font,
                command=lambda option_id=option.id: self.delete_option(option_id),
            ).grid(row=0, column=2, padx=(4, 8), pady=6)

    def select_category(self, category_id: int) -> None:
        self.selected_category_id = category_id
        self.render_categories()
        self.render_options()

    def add_category(self) -> None:
        try:
            category = self.tag_repository.add_category(self.category_entry.get())
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.category_entry.delete(0, "end")
        self.selected_category_id = category.id
        self.set_status(f"已新增上層標籤：{category.name}")
        self.reload()

    def add_option(self) -> None:
        if self.selected_category_id is None:
            self.set_status("請先選擇上層標籤。", error=True)
            return
        try:
            option = self.tag_repository.add_option(self.selected_category_id, self.option_entry.get())
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.option_entry.delete(0, "end")
        self.set_status(f"已新增下層標籤：{option.name}")
        self.reload()

    def disable_category(self, category_id: int) -> None:
        self.tag_repository.set_category_available(category_id, False)
        if self.selected_category_id == category_id:
            self.selected_category_id = None
        self.set_status("已停用上層標籤。")
        self.reload()

    def disable_option(self, option_id: int) -> None:
        self.tag_repository.set_option_available(option_id, False)
        self.set_status("已停用下層標籤。")
        self.reload()

    def move_category(self, category_id: int, direction: int) -> None:
        try:
            moved = self.tag_repository.move_category(category_id, direction)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        if not moved:
            self.set_status("已經在排序邊界。", error=True)
            return
        self.selected_category_id = category_id
        self.set_status("已更新上層標籤排序。")
        self.reload()

    def move_option(self, option_id: int, direction: int) -> None:
        try:
            moved = self.tag_repository.move_option(option_id, direction)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        if not moved:
            self.set_status("已經在排序邊界。", error=True)
            return
        self.set_status("已更新下層標籤排序。")
        self.reload()

    def restore_category(self, category_id: int) -> None:
        self.tag_repository.set_category_available(category_id, True)
        self.selected_category_id = category_id
        self.set_status("已恢復上層標籤。")
        self.reload()

    def restore_option(self, option_id: int) -> None:
        self.tag_repository.set_option_available(option_id, True)
        self.set_status("已恢復下層標籤。")
        self.reload()

    def delete_category(self, category_id: int) -> None:
        try:
            self.tag_repository.delete_category_if_unused(category_id)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.set_status("已刪除未使用的上層標籤。")
        self.reload()

    def delete_option(self, option_id: int) -> None:
        try:
            self.tag_repository.delete_option_if_unused(option_id)
        except Exception as exc:
            self.set_status(str(exc), error=True)
            return
        self.set_status("已刪除未使用的下層標籤。")
        self.reload()

    def current_category(self) -> TagCategory | None:
        for category in self.categories:
            if category.id == self.selected_category_id:
                return category
        return None

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#b3261e" if error else "#1b6e3c"
        self.status_label.configure(text=text, text_color=color)
        self.status_label.grid()

    def show_main_page(self) -> None:
        self.recovery_page.grid_remove()
        self.main_page.grid()
        self.reload()

    def show_recovery_page(self) -> None:
        self.main_page.grid_remove()
        self.recovery_page.grid()
        self.render_disabled()
